from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.services.llm.mcp_client import NETWORKX_API_URL
from common import models

# A large network's GraphML is built row by row on networkx-api.
EXPORT_TIMEOUT_SECONDS = 120.0


class NetworkNotFoundError(LookupError):
    """networkx-api has no network with the requested id."""


class NetworkExportError(RuntimeError):
    """networkx-api could not be reached or failed to build the GraphML."""


def _networkx_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=NETWORKX_API_URL, timeout=EXPORT_TIMEOUT_SECONDS)


async def export_graphml(network_id: int) -> str:
    """The network as a GraphML document, from networkx-api's REST export.

    Export is not an MCP tool: it is a user action, not something the agent
    does, so it stays off the model's tool surface.
    """
    try:
        async with _networkx_client() as client:
            response = await client.get(f"/api/v1/networks/{network_id}/export")
    except httpx.HTTPError as exc:
        raise NetworkExportError(f"networkx-api unreachable: {exc}") from exc

    if response.status_code == 404:
        raise NetworkNotFoundError(f"Network {network_id} not found")
    if response.status_code != 200:
        raise NetworkExportError(
            f"networkx-api export failed ({response.status_code}): "
            f"{response.text[:500]}"
        )
    graphml = response.json().get("graphml")
    if not isinstance(graphml, str):
        raise NetworkExportError("networkx-api export returned no GraphML")
    return graphml

# Upper bound on the parent chain walked to find a root. Subgraphs of subgraphs
# are legitimate, so this is a cycle/corruption stop, not a design limit.
MAX_NETWORK_DEPTH = 100


class NetworkService:
    """
    Service class for handling network-related business logic.
    """

    @staticmethod
    def root_network_id(network_id: int, db: Session) -> Optional[int]:
        """The root of `network_id`'s subgraph tree, or None if it cannot be found.

        None covers a missing network, a broken parent link, and a cycle.
        """
        current: Optional[int] = network_id
        seen = set()
        while current is not None and len(seen) < MAX_NETWORK_DEPTH:
            if current in seen:
                return None
            network = db.get(models.Network, current)
            if network is None:
                return None
            if network.parent_network_id is None:
                return network.id
            seen.add(current)
            current = network.parent_network_id
        return None

    @staticmethod
    def verify_network_access(network_id: int, user_id: int, db: Session) -> bool:
        """
        Verify if a user has access to a specific network.

        A user owns every network in the subgraph tree of each of their chats.
        Ownership is decided by the tree's root rather than by the network a
        chat currently points at: a chat that has switched into a subgraph
        still owns its root and the root's other subgraphs.

        Args:
            network_id: The ID of the network to check.
            user_id: The ID of the user requesting access.
            db: Database session.

        Returns:
            True if access is allowed, False otherwise.
        """
        target_root = NetworkService.root_network_id(network_id, db)
        if target_root is None:
            return False

        chat_network_ids = (
            db.query(models.Chat.network_id)
            .filter(models.Chat.user_id == user_id)
            .all()
        )
        return any(
            NetworkService.root_network_id(chat_network_id, db) == target_root
            for (chat_network_id,) in chat_network_ids
            if chat_network_id is not None
        )
