"""
モジュール名: layout_recommender.py
責務: ネットワーク説明からのレイアウト推薦
依存: services.llm.process_chat_message, re, json, logging
依存先: routers/chat.py

主要な関数:
- recommend_layout: ネットワークの説明と目的からレイアウトアルゴリズムを推薦

変更時の注意:
- LLMプロンプトはアルゴリズムの詳細を最新に保つ
- JSONパースエラーハンドリングを堅牢に
- 利用可能なレイアウト一覧はNetworkXMCPと同期する
"""

import re
import json
import logging
from typing import Dict, Any

from services.llm import process_chat_message

logger = logging.getLogger(__name__)

# レイアウト推薦のLLMプロンプトテンプレート
LAYOUT_RECOMMENDATION_PROMPT = """Based on the following network description and visualization purpose, recommend the most suitable graph layout algorithm.

Network Description: {description}

Visualization Purpose: {purpose}

Available layout algorithms:
- spring: Force-directed layout, good for general networks, shows clustering
- circular: Nodes arranged in a circle, good for showing cycles
- kamada_kawai: Force-directed with better aesthetics, good for small to medium networks
- fruchterman_reingold: Force-directed variant, good for general networks
- spectral: Uses graph spectrum, good for finding communities
- shell: Concentric circles, good for hierarchical or layered networks
- random: Random placement, baseline comparison

Please respond with a JSON object containing:
1. "recommended_layout": the name of the recommended layout (one of the above)
2. "explanation": a brief explanation of why this layout is suitable
3. "recommended_parameters": optional parameters for the layout (can be empty object)

Example response:
{{
  "recommended_layout": "spring",
  "explanation": "Spring layout is ideal for this network because it naturally reveals community structures and highlights hub nodes through force-directed positioning.",
  "recommended_parameters": {{"iterations": 50, "k": 0.1}}
}}

Respond ONLY with the JSON object, no additional text."""

# デフォルト推薦（フォールバック用）
DEFAULT_RECOMMENDATION = {
    "recommended_layout": "spring",
    "explanation": "Spring layout is a good default choice for most networks.",
    "recommended_parameters": {}
}


async def recommend_layout(description: str, purpose: str) -> Dict[str, Any]:
    """
    ネットワークの説明と目的からレイアウトを推薦

    Args:
        description: ネットワークの説明
        purpose: 可視化の目的

    Returns:
        推薦結果を含む辞書
        {
            "success": bool,
            "recommended_layout": str,
            "explanation": str,
            "recommended_parameters": dict
        }
    """
    if not description or not purpose:
        logger.warning("Empty description or purpose provided for layout recommendation")
        return {
            "success": False,
            "error": "Both description and purpose are required",
            **DEFAULT_RECOMMENDATION
        }

    try:
        # LLMプロンプト作成
        prompt = LAYOUT_RECOMMENDATION_PROMPT.format(
            description=description,
            purpose=purpose
        )

        # LLMを呼び出し
        messages = [{"role": "user", "content": prompt}]
        llm_response = await process_chat_message(messages)
        content = llm_response.get("content", "")

        # レスポンスからJSONを抽出
        recommendation = _extract_json_from_llm_response(content)

        # 結果を整形して返す
        return {
            "success": True,
            "recommended_layout": recommendation.get("recommended_layout", "spring"),
            "explanation": recommendation.get("explanation", ""),
            "recommended_parameters": recommendation.get("recommended_parameters", {})
        }

    except Exception as e:
        logger.error(f"Error in layout recommendation: {type(e).__name__}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Layout recommendation failed: {str(e)}",
            **DEFAULT_RECOMMENDATION
        }


def _extract_json_from_llm_response(content: str) -> Dict[str, Any]:
    """
    LLMレスポンスからJSONを抽出

    Args:
        content: LLMからのレスポンス文字列

    Returns:
        抽出されたJSON辞書、失敗時はデフォルト値
    """
    try:
        # まずレスポンス全体をJSONとしてパース
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 失敗した場合、テキスト内のJSON部分を正規表現で抽出
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError("No JSON found in LLM response")

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse JSON from LLM response: {e}")
        logger.debug(f"Raw LLM response: {content}")
        return DEFAULT_RECOMMENDATION


__all__ = ["recommend_layout"]