from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.services import usage_report
from app.services.llm.catalog import get_available_provider_catalog
from common import models

router = APIRouter(prefix="/users", tags=["users"])


def _settings(user: models.User) -> dict:
    return {
        "username": user.username,
        "default_provider": user.default_provider,
        "default_model": user.default_model,
    }


@router.get("/me/settings", response_model=schemas.UserSettings)
def read_settings(current_user: models.User = Depends(get_current_user)):
    """The current user's settings."""
    return _settings(current_user)


@router.patch("/me/settings", response_model=schemas.UserSettings)
def update_settings(
    body: schemas.UserSettingsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Set the provider/model used by chats that have not pinned their own.

    The pair must be one `GET /chat/providers` currently offers; send both as
    null to fall back to the server default.
    """
    provider, model = body.default_provider, body.default_model
    if (provider is None) != (model is None):
        raise HTTPException(
            status_code=422, detail="Set both provider and model, or neither"
        )
    if provider is not None:
        offered = {
            (p["id"], m["id"])
            for p in get_available_provider_catalog()
            for m in p["models"]
        }
        if (provider, model) not in offered:
            raise HTTPException(
                status_code=422, detail=f"Unavailable model: {provider}/{model}"
            )

    current_user.default_provider = provider
    current_user.default_model = model
    db.commit()
    db.refresh(current_user)
    return _settings(current_user)


@router.get("/me/usage", response_model=schemas.UserUsageReport)
def read_usage(
    days: Optional[int] = Query(
        30, ge=1, le=3650, description="Look back this many days; omit for 30."
    ),
    all_time: bool = Query(False, description="Ignore `days` and include everything."),
    tz: Optional[str] = Query(None, description="IANA time zone for daily totals."),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """The current user's LLM usage: totals, and per model, chat and day."""
    since = None if all_time else datetime.now(timezone.utc) - timedelta(days=days)
    return usage_report.user_usage(db, current_user.id, since=since, tz=tz)
