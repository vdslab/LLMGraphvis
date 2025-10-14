"""
MCP Client for NetworkX MCP Server
=================================

真のModel Context Protocol (MCP) クライアント実装
NetworkXMCPサーバーとMCPプロトコルで通信を行います。
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger("api.mcp_client")

class NetworkXMCPClient:
    """NetworkX MCP Server用のクライアント"""
    
    def __init__(self, server_url: str = "http://networkx-mcp:8001"):
        self.server_url = server_url.rstrip('/')
        self.client = None
        self._initialized = False
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーの開始"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        await self.close()
    
    async def initialize(self):
        """クライアントを初期化"""
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx is required for MCP client")
        
        if not self._initialized:
            self.client = httpx.AsyncClient(
                base_url=self.server_url,
                timeout=httpx.Timeout(60.0)
            )
            self._initialized = True
            logger.info(f"MCP Client initialized for {self.server_url}")
    
    async def close(self):
        """クライアントを閉じる"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("MCP Client closed")
    
    async def _call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """MCPツールを呼び出す"""
        if not self._initialized:
            await self.initialize()
        
        try:
            url = f"/tools/{tool_name}"
            logger.debug(f"Calling MCP tool: {tool_name} with parameters: {parameters}")
            
            response = await self.client.post(url, json=parameters)
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Tool {tool_name} response: {result}")
                return result
            else:
                error_msg = f"Tool {tool_name} failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
        
        except Exception as e:
            error_msg = f"Error calling tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_sample_network(self) -> Dict[str, Any]:
        """サンプルネットワークを取得"""
        try:
            if not self._initialized:
                await self.initialize()
            
            response = await self.client.get("/get_sample_network")
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"Failed to get sample network: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting sample network: {str(e)}"
            }
    
    async def calculate_and_store_centrality(
        self, 
        graphml_content: str, 
        centrality_type: str = "degree",
        centrality_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        中心性を計算し保存する（2段階処理の1段階目）
        """
        parameters = {
            "graphml_content": graphml_content,
            "centrality_type": centrality_type,
            "centrality_params": centrality_params or {}
        }
        
        result = await self._call_tool("calculate_and_store_centrality", parameters)
        
        if result.get("success"):
            logger.info(f"✅ Stage 1 completed: {centrality_type} centrality calculated and stored")
            if "result" in result:
                return result["result"]
        
        return result
    
    async def get_centrality_visualization(
        self,
        calculation_id: str,
        color_scheme: str = "viridis",
        size_range: List[float] = [10, 200]
    ) -> Dict[str, Any]:
        """
        保存された中心性データから可視化データを取得（2段階処理の2段階目）
        """
        parameters = {
            "calculation_id": calculation_id,
            "color_scheme": color_scheme,
            "size_range": size_range
        }
        
        result = await self._call_tool("get_centrality_visualization", parameters)
        
        if result.get("success"):
            logger.info(f"✅ Stage 2 completed: Visualization data generated for {calculation_id}")
            if "result" in result:
                return result["result"]
        
        return result
    
    async def calculate_centrality_two_stage(
        self,
        graphml_content: str,
        centrality_type: str = "degree",
        centrality_params: Optional[Dict[str, Any]] = None,
        color_scheme: str = "viridis", 
        size_range: List[float] = [10, 200]
    ) -> Dict[str, Any]:
        """
        2段階の中心性計算を実行（計算 → 可視化データ生成）
        """
        logger.info(f"🎯 Starting two-stage centrality calculation: {centrality_type}")
        
        # Stage 1: 計算と保存
        stage1_result = await self.calculate_and_store_centrality(
            graphml_content, centrality_type, centrality_params
        )
        
        if not stage1_result.get("success"):
            logger.error(f"❌ Stage 1 failed: {stage1_result.get('error')}")
            return {
                "success": False,
                "stage": 1,
                "error": stage1_result.get("error", "Stage 1 calculation failed")
            }
        
        calculation_id = stage1_result.get("calculation_id")
        if not calculation_id:
            logger.error("❌ Stage 1 did not return calculation_id")
            return {
                "success": False,
                "stage": 1,
                "error": "Stage 1 did not return calculation_id"
            }
        
        # Stage 2: 可視化データ生成
        stage2_result = await self.get_centrality_visualization(
            calculation_id, color_scheme, size_range
        )
        
        if not stage2_result.get("success"):
            logger.error(f"❌ Stage 2 failed: {stage2_result.get('error')}")
            return {
                "success": False,
                "stage": 2,
                "stage1_result": stage1_result,
                "error": stage2_result.get("error", "Stage 2 visualization failed")
            }
        
        # 両方のステージが成功
        logger.info(f"✅ Two-stage centrality calculation completed for {centrality_type}")
        return {
            "success": True,
            "centrality_type": centrality_type,
            "calculation_id": calculation_id,
            "stage1_result": stage1_result,
            "stage2_result": stage2_result,
            "visualization_data": stage2_result.get("visualization_data", {}),
            "metadata": stage2_result.get("metadata", {})
        }
    
    async def change_layout(
        self,
        graphml_content: str,
        layout_type: str = "spring",
        layout_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """レイアウトを変更"""
        parameters = {
            "graphml_content": graphml_content,
            "layout_type": layout_type,
            "layout_params": layout_params or {}
        }
        
        result = await self._call_tool("change_layout", parameters)
        
        if result.get("success"):
            logger.info(f"✅ Layout changed to {layout_type}")
            if "result" in result:
                return result["result"]
        
        return result
    
    async def list_centrality_calculations(self) -> Dict[str, Any]:
        """保存されている中心性計算のリストを取得"""
        result = await self._call_tool("list_centrality_calculations", {})
        
        if result.get("success"):
            if "result" in result:
                return result["result"]
        
        return result
    
    async def get_centrality_status(self, calculation_id: str) -> Dict[str, Any]:
        """中心性計算の状態を取得"""
        parameters = {"calculation_id": calculation_id}
        result = await self._call_tool("get_centrality_status", parameters)
        
        if result.get("success"):
            if "result" in result:
                return result["result"]
        
        return result

# コンテキストマネージャーのファクトリ関数
@asynccontextmanager
async def get_mcp_client(server_url: str = "http://networkx-mcp:8001"):
    """NetworkX MCP クライアントのコンテキストマネージャー"""
    client = NetworkXMCPClient(server_url)
    try:
        yield client
    finally:
        await client.close()