"""
モジュール名: tool_executor.py
責務: LLM Tool Call実行処理
依存: services.mcp_client, json, logging
依存先: services.chat_processor

主要な関数:
- execute_tool_call: LLM Tool Callを処理しMCPツール実行
- get_tool_result_summary: ツール実行結果をLLM用に加工

変更時の注意:
- Tool Call結果はLLM用に整形する必要がある
- エラーハンドリングを徹底する
- MCPサーバーに障害があった場合も適切なエラーメッセージを返す
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from services import mcp_client

logger = logging.getLogger(__name__)


async def execute_tool_call(
    tool_name: str,
    tool_args: Dict[str, Any],
    network_id: int
) -> Dict[str, Any]:
    """
    LLMツールコールを実行し結果を返す

    Args:
        tool_name: ツール名 ("calculate_centrality", "change_layout"等)
        tool_args: ツールに渡す引数
        network_id: 操作対象のネットワークID

    Returns:
        ツール実行結果とステータスを含む辞書
        {
            "success": bool,
            "details": Any,  # 成功時はツール結果、失敗時はエラー情報
            ...ツール固有の結果情報
        }
    """
    try:
        logger.info(f"Executing tool: {tool_name} for network {network_id}")
        
        # MCP clientを使用してツールを実行
        result = await mcp_client.execute_tool(tool_name, network_id, **tool_args)
        
        # MCPからの結果を取り出す (result内の"result"キー)
        mcp_result = result.get("result", {})
        
        # 結果が成功かどうか確認
        if mcp_result.get("success", True):
            logger.info(f"Tool execution successful: {tool_name}")
            # 成功結果を整形して返す
            return {
                "success": True,
                "details": mcp_result,
                **mcp_result  # ツール固有の結果情報も含める
            }
        else:
            # MCPサーバーからのエラー
            error_message = mcp_result.get("error", f"Unknown error from {tool_name}")
            logger.error(f"Tool execution failed: {error_message}")
            return {
                "success": False,
                "details": error_message
            }
            
    except mcp_client.MCPError as e:
        # MCP接続・処理エラー
        logger.error(f"MCP error in execute_tool_call: {e.message}")
        return {
            "success": False,
            "details": f"Tool execution failed: {e.message}"
        }
    except Exception as e:
        # 予期せぬエラー
        logger.error(f"Unexpected error in execute_tool_call: {type(e).__name__}: {e}", exc_info=True)
        return {
            "success": False,
            "details": f"Unexpected error: {str(e)}"
        }


def get_tool_result_for_llm(tool_result: Dict[str, Any]) -> str:
    """
    ツール実行結果をLLMに返すための文字列に変換

    Args:
        tool_result: execute_tool_callからの戻り値

    Returns:
        LLMに返すJSON文字列
    """
    # ツール結果からLLMに伝えるべき情報を抽出
    # 中心性計算の場合は特別な処理
    if "centrality_values" in tool_result:
        core_result = tool_result["centrality_values"]
    else:
        core_result = tool_result

    # 結果のステータスに応じて異なる形式を返す
    if tool_result.get("success", True):
        result_for_llm = {
            "status": "success",
            "details": core_result
        }
    else:
        result_for_llm = {
            "status": "error",
            "details": tool_result.get("details", "Unknown error from tool")
        }
    
    return json.dumps(result_for_llm)


__all__ = ["execute_tool_call", "get_tool_result_for_llm"]