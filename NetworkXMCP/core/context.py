"""
Core server context and shared resources.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("networkx_mcp.core")


@dataclass
class ServerContext:
    """Server context with shared resources."""
    graph_cache: Dict[str, Any] = field(default_factory=dict)
    centrality_cache: Dict[str, Any] = field(default_factory=dict)
    calculation_history: Dict[str, Any] = field(default_factory=dict)

    def clear_caches(self) -> None:
        """Clear all caches."""
        self.graph_cache.clear()
        self.centrality_cache.clear()
        self.calculation_history.clear()
        logger.info("All caches cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "graphs": len(self.graph_cache),
            "centrality_calculations": len(self.centrality_cache),
            "calculation_history": len(self.calculation_history)
        }
