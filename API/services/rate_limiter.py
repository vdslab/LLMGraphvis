"""
Rate limiting service for API endpoints.
Uses slowapi for rate limiting with configurable limits.
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


def get_rate_limit_key(request: Request):
    """
    Get rate limiting key based on user authentication status.

    - For authenticated users with personal API keys: use user ID
    - For users using shared .env API keys: use IP address with stricter limits
    """
    # Check if user has provided personal API keys
    # This would be determined by checking if they've set custom keys in their session
    # For now, we'll use IP-based limiting for all users
    return get_remote_address(request)


def get_rate_limit_for_user(request: Request) -> str:
    """
    Get appropriate rate limit based on user's API key status.

    Returns:
        Rate limit string (e.g., "100/hour")
    """
    # Get default rate limit from environment
    default_limit = os.environ.get("DEFAULT_RATE_LIMIT", "100")

    # TODO: In future, check if user has personal API keys
    # If they have personal keys, could allow higher limits
    # For now, apply default limit to all users

    return f"{default_limit}/hour"


# Initialize the limiter
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[get_rate_limit_for_user],
    headers_enabled=True,
    storage_uri="memory://",  # Use in-memory storage for simplicity
)

# Helper function to get current rate limit


def get_current_rate_limit() -> str:
    """Get the current rate limit setting."""
    return os.environ.get("DEFAULT_RATE_LIMIT", "100")


def update_rate_limit(new_limit: int) -> None:
    """Update the rate limit setting."""
    os.environ["DEFAULT_RATE_LIMIT"] = str(new_limit)
    logger.info(f"Updated rate limit to {new_limit} requests per hour")
