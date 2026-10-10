from typing import Optional

from sqlalchemy.orm import Session

from common import models

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
