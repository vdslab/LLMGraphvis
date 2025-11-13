"""
NetworkX MCP Client Service.

This module provides a client for interacting with the NetworkX MCP service,
centralizing all API calls and providing consistent error handling.
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, Union, List

# Configure logging
logger = logging.getLogger(__name__)

# NetworkXMCPサーバーとの通信用URL
NETWORKX_MCP_URL = os.environ.get("NETWORKX_MCP_URL", "http://networkx-mcp:8001")
DEFAULT_TIMEOUT = 60.0  # seconds

class MCPError(Exception):
    """Exception raised for errors in the MCP service."""
    
    def __init__(self, message: str, status_code: int = 500, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the MCPError.
        
        Args:
            message: The error message.
            status_code: The HTTP status code.
            context: Additional context for the error.
        """
        self.message = message
        self.status_code = status_code
        self.context = context or {}
        super().__init__(self.message)

async def convert_graphml(graphml_content: str) -> Dict[str, Any]:
    """
    Convert GraphML content to a standardized format.
    
    Args:
        graphml_content: The GraphML content to convert.
        
    Returns:
        A dictionary containing the standardized GraphML content.
        
    Raises:
        MCPError: If the conversion fails.
    """
    try:
        url = f"{NETWORKX_MCP_URL}/tools/convert_graphml"
        payload = {"graphml_content": graphml_content}
        
        logger.info(f"Sending GraphML to NetworkXMCP for conversion: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            
        if response.status_code != 200:
            error_msg = f"Error from NetworkXMCP: {response.text}"
            logger.error(error_msg)
            raise MCPError(
                message=error_msg,
                status_code=response.status_code,
                context={"url": url}
            )
        
        result = response.json()
        
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error from NetworkXMCP")
            logger.error(f"Error: {error_msg}")
            raise MCPError(
                message=error_msg,
                status_code=400,
                context={"url": url}
            )
        
        logger.info(f"Successfully converted GraphML, content length: {len(result.get('graphml_content', ''))}")
        return result
    
    except httpx.TimeoutException:
        error_msg = "Timeout while connecting to NetworkXMCP"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=504,
            context={"url": url}
        )
    
    except httpx.RequestError as e:
        error_msg = f"Request error while connecting to NetworkXMCP: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=502,
            context={"url": url}
        )
    
    except Exception as e:
        error_msg = f"Unexpected error in convert_graphml: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=500,
            context={"url": url}
        )

async def change_layout(network_id: int, layout_type: str = "spring", layout_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Change the layout of a network.
    
    Args:
        network_id: The ID of the network.
        layout_type: The type of layout to apply.
        layout_params: Parameters for the layout algorithm.
        
    Returns:
        A dictionary containing the result of the layout change.
        
    Raises:
        MCPError: If the layout change fails.
    """
    try:
        url = f"{NETWORKX_MCP_URL}/tools/change_layout"
        payload = {
            "network_id": network_id,
            "layout_type": layout_type,
            "layout_params": layout_params or {}
        }
        
        logger.info(f"Requesting layout change for network {network_id} with layout {layout_type}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            
        if response.status_code != 200:
            error_msg = f"Error from NetworkXMCP: {response.text}"
            logger.error(error_msg)
            raise MCPError(
                message=error_msg,
                status_code=response.status_code,
                context={"url": url, "network_id": network_id, "layout_type": layout_type}
            )
        
        result = response.json()
        
        # Check if the result contains the expected data
        if not result.get("result", {}).get("success"):
            error_msg = result.get("result", {}).get("error", "Unknown error from NetworkXMCP")
            logger.error(f"Error: {error_msg}")
            raise MCPError(
                message=error_msg,
                status_code=400,
                context={"url": url, "network_id": network_id, "layout_type": layout_type}
            )
        
        logger.info(f"Successfully changed layout for network {network_id} to {layout_type}")
        return result
    
    except httpx.TimeoutException:
        error_msg = "Timeout while connecting to NetworkXMCP"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=504,
            context={"url": url, "network_id": network_id, "layout_type": layout_type}
        )
    
    except httpx.RequestError as e:
        error_msg = f"Request error while connecting to NetworkXMCP: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=502,
            context={"url": url, "network_id": network_id, "layout_type": layout_type}
        )
    
    except Exception as e:
        error_msg = f"Unexpected error in change_layout: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=500,
            context={"url": url, "network_id": network_id, "layout_type": layout_type}
        )

async def calculate_centrality(network_id: int, centrality_type: str, centrality_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calculate centrality metrics for a network.
    
    Args:
        network_id: The ID of the network.
        centrality_type: The type of centrality to calculate.
        centrality_params: Parameters for the centrality calculation.
        
    Returns:
        A dictionary containing the result of the centrality calculation.
        
    Raises:
        MCPError: If the centrality calculation fails.
    """
    try:
        url = f"{NETWORKX_MCP_URL}/tools/calculate_centrality"
        payload = {
            "network_id": network_id,
            "centrality_type": centrality_type,
            "centrality_params": centrality_params or {}
        }
        
        logger.info(f"Calculating {centrality_type} centrality for network {network_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            
        if response.status_code != 200:
            error_msg = f"Error from NetworkXMCP: {response.text}"
            logger.error(error_msg)
            raise MCPError(
                message=error_msg,
                status_code=response.status_code,
                context={"url": url, "network_id": network_id, "centrality_type": centrality_type}
            )
        
        result = response.json()
        
        # Check if the result contains the expected data
        if not result.get("result", {}).get("success"):
            error_msg = result.get("result", {}).get("error", "Unknown error from NetworkXMCP")
            logger.error(f"Error: {error_msg}")
            raise MCPError(
                message=error_msg,
                status_code=400,
                context={"url": url, "network_id": network_id, "centrality_type": centrality_type}
            )
        
        logger.info(f"Successfully calculated {centrality_type} centrality for network {network_id}")
        return result
    
    except httpx.TimeoutException:
        error_msg = "Timeout while connecting to NetworkXMCP"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=504,
            context={"url": url, "network_id": network_id, "centrality_type": centrality_type}
        )
    
    except httpx.RequestError as e:
        error_msg = f"Request error while connecting to NetworkXMCP: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=502,
            context={"url": url, "network_id": network_id, "centrality_type": centrality_type}
        )
    
    except Exception as e:
        error_msg = f"Unexpected error in calculate_centrality: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=500,
            context={"url": url, "network_id": network_id, "centrality_type": centrality_type}
        )

async def apply_metric_to_visual(
    network_id: int,
    metric: str = "degree_centrality",
    visual: str = "node_size",
    mapping: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    メトリック値を視覚属性に適用します。
    
    Args:
        network_id: ネットワークID
        metric: 適用するメトリック（例：degree_centrality）
        visual: 適用先の視覚属性（例：node_size, node_color）
        mapping: マッピングパラメータ（例：{"min_size": 5, "max_size": 20}）
        
    Returns:
        処理結果を含む辞書
        
    Raises:
        MCPError: 処理に失敗した場合
    """
    try:
        url = f"{NETWORKX_MCP_URL}/tools/apply_metric_to_visual"
        payload = {
            "network_id": network_id,
            "metric": metric,
            "visual": visual,
            "mapping": mapping or {}
        }
        
        logger.info(f"Applying {metric} to {visual} for network {network_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            
        if response.status_code != 200:
            error_msg = f"Error from NetworkXMCP: {response.text}"
            logger.error(error_msg)
            raise MCPError(
                message=error_msg,
                status_code=response.status_code,
                context={"url": url, "network_id": network_id, "metric": metric, "visual": visual}
            )
        
        result = response.json()
        
        # Check if the result contains the expected data
        if not result.get("result", {}).get("success", True):
            error_msg = result.get("result", {}).get("error", "Unknown error from NetworkXMCP")
            logger.error(f"Error: {error_msg}")
            raise MCPError(
                message=error_msg,
                status_code=400,
                context={"url": url, "network_id": network_id, "metric": metric, "visual": visual}
            )
        
        logger.info(f"Successfully applied {metric} to {visual} for network {network_id}")
        return result
    
    except httpx.TimeoutException:
        error_msg = "Timeout while connecting to NetworkXMCP"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=504,
            context={"url": url, "network_id": network_id, "metric": metric, "visual": visual}
        )
    
    except httpx.RequestError as e:
        error_msg = f"Request error while connecting to NetworkXMCP: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=502,
            context={"url": url, "network_id": network_id, "metric": metric, "visual": visual}
        )
    
    except Exception as e:
        error_msg = f"Unexpected error in apply_metric_to_visual: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=500,
            context={"url": url, "network_id": network_id, "metric": metric, "visual": visual}
        )

async def execute_tool(tool_name: str, network_id: int, **kwargs) -> Dict[str, Any]:
    """
    Execute a tool on the NetworkX MCP service.
    
    Args:
        tool_name: The name of the tool to execute.
        network_id: The ID of the network.
        **kwargs: Additional arguments for the tool.
        
    Returns:
        A dictionary containing the result of the tool execution.
        
    Raises:
        MCPError: If the tool execution fails.
    """
    try:
        url = f"{NETWORKX_MCP_URL}/tools/{tool_name}"
        payload = {
            "network_id": network_id,
            **kwargs
        }
        
        logger.info(f"Executing tool {tool_name} for network {network_id}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            
        if response.status_code != 200:
            error_msg = f"Error from NetworkXMCP: {response.text}"
            logger.error(error_msg)
            raise MCPError(
                message=error_msg,
                status_code=response.status_code,
                context={"url": url, "network_id": network_id, "tool_name": tool_name}
            )
        
        result = response.json()
        
        # Check if the result contains the expected data
        if not result.get("result", {}).get("success", True):
            error_msg = result.get("result", {}).get("error", "Unknown error from NetworkXMCP")
            logger.error(f"Error: {error_msg}")
            raise MCPError(
                message=error_msg,
                status_code=400,
                context={"url": url, "network_id": network_id, "tool_name": tool_name}
            )
        
        logger.info(f"Successfully executed tool {tool_name} for network {network_id}")
        return result
    
    except httpx.TimeoutException:
        error_msg = "Timeout while connecting to NetworkXMCP"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=504,
            context={"url": url, "network_id": network_id, "tool_name": tool_name}
        )
    
    except httpx.RequestError as e:
        error_msg = f"Request error while connecting to NetworkXMCP: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=502,
            context={"url": url, "network_id": network_id, "tool_name": tool_name}
        )
    
    except Exception as e:
        error_msg = f"Unexpected error in execute_tool: {str(e)}"
        logger.error(error_msg)
        raise MCPError(
            message=error_msg,
            status_code=500,
            context={"url": url, "network_id": network_id, "tool_name": tool_name}
        )