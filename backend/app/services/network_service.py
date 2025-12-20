from sqlalchemy.orm import Session

from app import models


class NetworkService:
    """
    Service class for handling network-related business logic.
    """

    @staticmethod
    def verify_network_access(network_id: int, user_id: int, db: Session) -> bool:
        """
        Verify if a user has access to a specific network.

        Logic:
        1. Check direct ownership via Chat (Network -> Chat -> User).
        2. If network is a subgraph, traverse up to the parent network recursively
           and check ownership of the parent.

        Args:
            network_id: The ID of the network to check.
            user_id: The ID of the user requesting access.
            db: Database session.

        Returns:
            True if access is allowed, False otherwise.
        """
        # Check direct ownership via Chat
        chat = (
            db.query(models.Chat)
            .filter(
                models.Chat.network_id == network_id, models.Chat.user_id == user_id
            )
            .first()
        )

        if chat:
            return True

        # Check if it's a subgraph (traverse up)
        current_id = network_id

        # Limit depth to avoid infinite loops if cycle exists (should not happen in DAG)
        MAX_DEPTH = 10
        for _ in range(MAX_DEPTH):
            network = db.query(models.Network).get(current_id)
            if not network:
                return False

            if network.parent_network_id:
                current_id = network.parent_network_id

                # Check permission for the parent network (via associated chat)
                # Note: Currently, we assume if you own the parent, you own the subgraph.
                # Access is controlled via Chat ownership.
                chat = (
                    db.query(models.Chat)
                    .filter(
                        models.Chat.network_id == current_id,
                        models.Chat.user_id == user_id,
                    )
                    .first()
                )

                if chat:
                    return True
            else:
                # Reached root with no match
                return False

        return False
