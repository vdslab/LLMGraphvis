"""
グラフキャッシュモジュール
===================

計算済みのグラフオブジェクトをメモリ上に保持し、
計算と表示の分離を実現するためのキャッシュ機能を提供します。
"""

import networkx as nx
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import threading

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.graph_cache")

class GraphCache:
    """
    グラフオブジェクトをメモリ上にキャッシュするクラス
    """
    
    def __init__(self, max_size=100, ttl_minutes=60):
        """
        初期化
        
        Args:
            max_size (int): キャッシュの最大サイズ
            ttl_minutes (int): キャッシュの有効期限（分）
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.Lock()
        logger.info(f"GraphCache initialized with max_size={max_size}, ttl={ttl_minutes}min")
    
    def store(self, graph: nx.Graph, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        グラフをキャッシュに保存し、一意のIDを返す
        
        Args:
            graph (nx.Graph): 保存するグラフ
            metadata (dict, optional): グラフに関連するメタデータ
            
        Returns:
            str: グラフの一意のID
        """
        with self._lock:
            # キャッシュサイズの制限チェック
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            
            # 一意のIDを生成
            graph_id = str(uuid.uuid4())
            
            # グラフとメタデータを保存
            self._cache[graph_id] = {
                "graph": graph,
                "metadata": metadata or {},
                "created_at": datetime.now(),
                "last_accessed": datetime.now()
            }
            
            logger.info(f"Stored graph with ID: {graph_id} (cache size: {len(self._cache)})")
            return graph_id
    
    def get(self, graph_id: str) -> Optional[nx.Graph]:
        """
        IDに基づいてグラフを取得する
        
        Args:
            graph_id (str): グラフのID
            
        Returns:
            nx.Graph or None: グラフオブジェクト、存在しない場合はNone
        """
        with self._lock:
            if graph_id not in self._cache:
                logger.warning(f"Graph ID not found: {graph_id}")
                return None
            
            # TTLチェック
            cache_entry = self._cache[graph_id]
            if datetime.now() - cache_entry["created_at"] > self._ttl:
                logger.info(f"Graph ID expired: {graph_id}")
                del self._cache[graph_id]
                return None
            
            # 最終アクセス時刻を更新
            cache_entry["last_accessed"] = datetime.now()
            logger.debug(f"Retrieved graph with ID: {graph_id}")
            return cache_entry["graph"]
    
    def get_metadata(self, graph_id: str) -> Optional[Dict[str, Any]]:
        """
        IDに基づいてメタデータを取得する
        
        Args:
            graph_id (str): グラフのID
            
        Returns:
            dict or None: メタデータ、存在しない場合はNone
        """
        with self._lock:
            if graph_id not in self._cache:
                return None
            
            cache_entry = self._cache[graph_id]
            if datetime.now() - cache_entry["created_at"] > self._ttl:
                del self._cache[graph_id]
                return None
            
            return cache_entry["metadata"]
    
    def update_metadata(self, graph_id: str, metadata: Dict[str, Any]) -> bool:
        """
        メタデータを更新する
        
        Args:
            graph_id (str): グラフのID
            metadata (dict): 更新するメタデータ
            
        Returns:
            bool: 更新が成功したかどうか
        """
        with self._lock:
            if graph_id not in self._cache:
                logger.warning(f"Cannot update metadata: Graph ID not found: {graph_id}")
                return False
            
            self._cache[graph_id]["metadata"].update(metadata)
            self._cache[graph_id]["last_accessed"] = datetime.now()
            logger.debug(f"Updated metadata for graph ID: {graph_id}")
            return True
    
    def delete(self, graph_id: str) -> bool:
        """
        グラフをキャッシュから削除する
        
        Args:
            graph_id (str): グラフのID
            
        Returns:
            bool: 削除が成功したかどうか
        """
        with self._lock:
            if graph_id in self._cache:
                del self._cache[graph_id]
                logger.info(f"Deleted graph with ID: {graph_id}")
                return True
            return False
    
    def clear(self):
        """
        キャッシュをクリアする
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared cache ({count} graphs removed)")
    
    def _evict_oldest(self):
        """
        最も古いエントリを削除する（LRU方式）
        """
        if not self._cache:
            return
        
        # 最終アクセス時刻が最も古いエントリを見つける
        oldest_id = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["last_accessed"]
        )
        
        del self._cache[oldest_id]
        logger.info(f"Evicted oldest graph: {oldest_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        キャッシュの統計情報を取得する
        
        Returns:
            dict: 統計情報
        """
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_minutes": self._ttl.total_seconds() / 60,
                "graph_ids": list(self._cache.keys())
            }
    
    def cleanup_expired(self):
        """
        期限切れのエントリを削除する
        """
        with self._lock:
            now = datetime.now()
            expired_ids = [
                graph_id for graph_id, entry in self._cache.items()
                if now - entry["created_at"] > self._ttl
            ]
            
            for graph_id in expired_ids:
                del self._cache[graph_id]
            
            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired graphs")


# グローバルキャッシュインスタンス
_global_cache = None

def get_cache() -> GraphCache:
    """
    グローバルキャッシュインスタンスを取得する
    
    Returns:
        GraphCache: グローバルキャッシュインスタンス
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = GraphCache()
    return _global_cache

def reset_cache():
    """
    グローバルキャッシュをリセットする
    """
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
    _global_cache = None
    logger.info("Global cache reset")
