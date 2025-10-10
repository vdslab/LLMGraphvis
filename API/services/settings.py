"""
Settings service for managing LLM provider configuration.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages LLM provider settings and configuration."""

    def __init__(self):
        self.env_file_path = Path.cwd() / ".env"
        self._runtime_config = {}

    def get_current_settings(self) -> Dict[str, Any]:
        """Get current LLM provider settings."""
        return {
            "provider": os.environ.get("LLM_PROVIDER", "google").lower(),
            "has_google_api_key": bool(os.environ.get("GOOGLE_API_KEY")),
            "has_openai_api_key": bool(os.environ.get("OPENAI_API_KEY")),
            "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
            "available_providers": ["google", "openai"]
        }

    def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update LLM provider settings.

        Args:
            settings: Dictionary containing new settings

        Returns:
            Updated settings dictionary

        Raises:
            ValueError: If invalid provider or missing required keys
        """
        provider = settings.get("provider")
        if provider and provider not in ["google", "openai"]:
            raise ValueError(
                f"Invalid provider: {provider}. Must be 'google' or 'openai'.")

        # Validate required API keys
        if provider == "google" and not settings.get("google_api_key"):
            if not os.environ.get("GOOGLE_API_KEY"):
                raise ValueError(
                    "Google API key is required when using Google provider.")

        if provider == "openai" and not settings.get("openai_api_key"):
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError(
                    "OpenAI API key is required when using OpenAI provider.")

        # Update environment variables
        if provider:
            os.environ["LLM_PROVIDER"] = provider

        if settings.get("google_api_key"):
            os.environ["GOOGLE_API_KEY"] = settings["google_api_key"]

        if settings.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = settings["openai_api_key"]

        if settings.get("openai_model"):
            os.environ["OPENAI_MODEL"] = settings["openai_model"]

        # Update runtime config
        self._runtime_config.update(settings)

        # Persist to .env file
        self._update_env_file(settings)

        # Reload LLM service with new settings
        self._reload_llm_service(provider)

        return self.get_current_settings()

    def _update_env_file(self, settings: Dict[str, Any]) -> None:
        """Update the .env file with new settings."""
        if not self.env_file_path.exists():
            logger.warning(f".env file not found at {self.env_file_path}")
            return

        try:
            # Read current .env file
            with open(self.env_file_path, 'r') as f:
                lines = f.readlines()

            # Update relevant lines
            updated_lines = []
            updated_keys = set()

            for line in lines:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()

                    if key == "LLM_PROVIDER" and "provider" in settings:
                        updated_lines.append(
                            f"LLM_PROVIDER={settings['provider']}\n")
                        updated_keys.add("provider")
                    elif key == "GOOGLE_API_KEY" and "google_api_key" in settings:
                        updated_lines.append(
                            f'GOOGLE_API_KEY="{settings["google_api_key"]}"\n')
                        updated_keys.add("google_api_key")
                    elif key == "OPENAI_API_KEY" and "openai_api_key" in settings:
                        updated_lines.append(
                            f'OPENAI_API_KEY="{settings["openai_api_key"]}"\n')
                        updated_keys.add("openai_api_key")
                    elif key == "OPENAI_MODEL" and "openai_model" in settings:
                        updated_lines.append(
                            f'OPENAI_MODEL="{settings["openai_model"]}"\n')
                        updated_keys.add("openai_model")
                    else:
                        updated_lines.append(line + '\n')
                else:
                    updated_lines.append(line + '\n')

            # Add any new settings that weren't found in the file
            for key, value in settings.items():
                if key not in updated_keys and value is not None:
                    if key == "provider":
                        updated_lines.append(f"LLM_PROVIDER={value}\n")
                    elif key == "google_api_key":
                        updated_lines.append(f'GOOGLE_API_KEY="{value}"\n')
                    elif key == "openai_api_key":
                        updated_lines.append(f'OPENAI_API_KEY="{value}"\n')
                    elif key == "openai_model":
                        updated_lines.append(f'OPENAI_MODEL="{value}"\n')

            # Write back to .env file
            with open(self.env_file_path, 'w') as f:
                f.writelines(updated_lines)

            logger.info("Successfully updated .env file")

        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")
            raise

    def _reload_llm_service(self, provider: Optional[str] = None) -> None:
        """Reload the LLM service with new configuration."""
        try:
            from services.llm import reload_llm_service
            reload_llm_service()
            logger.info(
                f"Successfully reloaded LLM service with provider: {provider}")
        except Exception as e:
            logger.error(f"Failed to reload LLM service: {e}")
            # Don't raise here as the settings have been updated successfully


# Global settings manager instance
settings_manager = SettingsManager()
