"""
Settings router for LLM provider configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

import models
import schemas
import auth
from database import get_db
from services.settings import settings_manager

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={401: {"description": "Unauthorized"}},
)

logger = logging.getLogger(__name__)


@router.get("/llm-provider", response_model=schemas.LLMProviderResponse)
async def get_llm_provider_settings(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current LLM provider settings."""
    try:
        settings = settings_manager.get_current_settings()
        return schemas.LLMProviderResponse(**settings)
    except Exception as e:
        logger.error(f"Error getting LLM provider settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get LLM provider settings")


@router.put("/llm-provider", response_model=schemas.LLMProviderResponse)
async def update_llm_provider_settings(
    settings: schemas.LLMProviderUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update LLM provider settings."""
    try:
        # Convert pydantic model to dict, excluding None values
        settings_dict = settings.model_dump(exclude_none=True)

        if not settings_dict:
            raise HTTPException(status_code=400, detail="No settings provided")

        updated_settings = settings_manager.update_settings(settings_dict)
        return schemas.LLMProviderResponse(**updated_settings)

    except ValueError as e:
        logger.error(f"Validation error updating LLM provider settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating LLM provider settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update LLM provider settings")


@router.get("/llm-provider/status")
async def get_llm_provider_status(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get LLM provider status and health check."""
    try:
        settings = settings_manager.get_current_settings()
        provider = settings["provider"]

        # Basic health check
        status = {
            "provider": provider,
            "status": "unknown",
            "has_required_keys": False,
            "message": ""
        }

        if provider == "google":
            if settings["has_google_api_key"]:
                status["has_required_keys"] = True
                status["status"] = "ready"
                status["message"] = "Google API key is configured"
            else:
                status["status"] = "error"
                status["message"] = "Google API key is missing"

        elif provider == "openai":
            if settings["has_openai_api_key"]:
                status["has_required_keys"] = True
                status["status"] = "ready"
                status["message"] = "OpenAI API key is configured"
            else:
                status["status"] = "error"
                status["message"] = "OpenAI API key is missing"
        else:
            status["status"] = "error"
            status["message"] = f"Unknown provider: {provider}"

        return status

    except Exception as e:
        logger.error(f"Error getting LLM provider status: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get LLM provider status")
