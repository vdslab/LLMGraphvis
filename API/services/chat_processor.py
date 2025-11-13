"""
モジュール名: chat_processor.py
責務: チャットメッセージ処理とLLM統合
依存: services.llm, services.tool_executor, services.conversation_service
依存先: routers/chat.py

主要な関数:
- process_user_message: ユーザーメッセージをLLMで処理し応答を生成
- process_message_with_llm: LLMでメッセージを処理
- format_messages_for_llm: メッセージ履歴をLLM用に整形

変更時の注意:
- LLMレスポンス形式が変わった場合は format_messages_for_llm も更新
- ツールコール処理ロジックは常に最新の仕様に合わせる
"""

import json
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

import models
from services import llm
from services.conversation_service import get_conversation_messages, save_message
from services.tool_executor import execute_tool_call, get_tool_result_for_llm

logger = logging.getLogger(__name__)


def format_messages_for_llm(messages: List[models.ChatMessage]) -> List[Dict[str, str]]:
    """
    データベースから取得したメッセージをLLM用フォーマットに変換

    Args:
        messages: データベースメッセージ

    Returns:
        LLM用メッセージリスト
    """
    formatted = []
    for msg in messages:
        # メタデータを処理（ツールコールを含むメッセージなど）
        if msg.meta_data and msg.meta_data != "{}":
            try:
                meta = json.loads(msg.meta_data)
                # ツールコールを含む場合、元のLLMレスポンスを使用
                if msg.role == "assistant" and "tool_calls" in meta:
                    formatted.append({"role": "assistant", "content": json.dumps(meta)})
                    continue
            except (json.JSONDecodeError, TypeError):
                pass  # メタデータが不正な場合は無視
        
        # 通常のメッセージ処理
        formatted.append({"role": msg.role, "content": msg.content})
    
    return formatted


async def process_message_with_llm(
    message_history: List[Dict[str, str]], 
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    LLMを使ってメッセージを処理

    Args:
        message_history: LLM用に整形されたメッセージ履歴
        model: 使用するLLMモデル名（オプション）

    Returns:
        LLMからのレスポンス
    """
    try:
        return await llm.process_chat_message(message_history, model=model)
    except Exception as e:
        logger.error(f"Error processing message with LLM: {type(e).__name__}: {e}", exc_info=True)
        return {"content": f"LLMでの処理中にエラーが発生しました: {str(e)}"}


async def process_user_message(
    conversation_id: int,
    user_message: str,
    user_id: int,
    db: Session,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    ユーザーメッセージを処理し、LLMレスポンスを生成

    ワークフロー:
    1. ユーザーメッセージを保存
    2. 会話履歴を取得
    3. LLM呼び出し
    4. 必要に応じてツール実行
    5. 最終レスポンスを生成し保存

    Args:
        conversation_id: 会話ID
        user_message: ユーザーメッセージ内容
        user_id: ユーザーID
        db: DBセッション
        model: 使用するLLMモデル名（オプション）

    Returns:
        処理結果を含む辞書:
        {
            "success": bool,
            "content": str,  # 応答メッセージ
            "conversation_id": int,
            "networkUpdate": object | None  # ネットワーク更新情報（該当する場合）
        }
    """
    try:
        # 1. ユーザーメッセージ正規化と保存
        if isinstance(user_message, dict):
            normalized_message = json.dumps(user_message)
        else:
            normalized_message = str(user_message)
        
        # メッセージを保存
        save_message(db, conversation_id, "user", normalized_message, user_id)
        
        # 2. 会話履歴取得
        db_messages = get_conversation_messages(db, conversation_id, user_id)
        formatted_history = format_messages_for_llm(db_messages)
        
        # 3. LLM呼び出し
        llm_response = await process_message_with_llm(formatted_history, model)
        
        # LLMエラー発生時
        if "error" in llm_response:
            error_message = f"LLM処理エラー: {llm_response.get('error')}"
            save_message(db, conversation_id, "assistant", error_message, user_id)
            return {
                "success": False,
                "content": error_message,
                "conversation_id": conversation_id,
                "networkUpdate": None
            }
        
        # 4. ツールコール処理
        network_update_info = None
        tool_calls = llm_response.get("tool_calls")
        
        if tool_calls:
            # 最初のツールコールを処理（現在は複数ツールコールに非対応）
            tool_call = tool_calls[0]
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            # DBから関連ネットワークのIDを取得
            db_conversation = db.query(models.Conversation).get(conversation_id)
            network_id = db_conversation.network.id
            
            # ツール実行
            tool_result = await execute_tool_call(tool_name, tool_args, network_id)
            
            if tool_result.get("success", True):
                network_update_info = {"type": tool_name, **tool_result}
            
            # ツール結果をLLM用に整形
            tool_result_content = get_tool_result_for_llm(tool_result)
            
            # ツール実行結果をLLMに渡して最終レスポンス生成
            final_history = formatted_history + [
                {"role": "assistant", "content": json.dumps({"tool_calls": tool_calls})},
                {"role": "tool", "content": tool_result_content}
            ]
            
            final_llm_response = await process_message_with_llm(final_history, model)
            final_assistant_content = final_llm_response.get("content", "処理が完了しました。")
        else:
            # ツールコールがない場合は直接LLMレスポンスを使用
            final_assistant_content = llm_response.get("content", "応答を生成できませんでした。")
        
        # 5. 最終レスポンスを保存
        save_message(
            db, 
            conversation_id, 
            "assistant", 
            final_assistant_content, 
            user_id,
        )
        
        return {
            "success": True,
            "content": final_assistant_content,
            "conversation_id": conversation_id,
            "networkUpdate": network_update_info
        }
    
    except Exception as e:
        logger.error(f"Error in process_user_message: {type(e).__name__}: {e}", exc_info=True)
        error_message = f"メッセージ処理中にエラーが発生しました: {str(e)}"
        
        try:
            # エラーメッセージを保存
            save_message(db, conversation_id, "assistant", error_message, user_id)
        except Exception as save_error:
            logger.error(f"Failed to save error message: {save_error}")
        
        return {
            "success": False,
            "content": error_message,
            "conversation_id": conversation_id,
            "networkUpdate": None,
            "error_code": "PROCESS_ERROR",
            "context": {"error_type": type(e).__name__}
        }


__all__ = ["process_user_message", "format_messages_for_llm"]