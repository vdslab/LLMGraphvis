from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import EvaluationConfig
from .visualization import diff_visualizations, summarize_visualization


def _compact(value: Any, depth: int = 0) -> Any:
    if depth >= 5:
        return "[nested value omitted]"
    if isinstance(value, str):
        return value if len(value) <= 4000 else value[:4000] + "… [truncated]"
    if isinstance(value, list):
        items = [_compact(item, depth + 1) for item in value[:30]]
        if len(value) > 30:
            items.append(f"[{len(value) - 30} items omitted]")
        return items
    if isinstance(value, dict):
        return {str(key): _compact(item, depth + 1) for key, item in value.items()}
    return value


@dataclass
class StartedChat:
    chat_id: int
    network_id: int
    initial_state: dict[str, Any]


class GraphVisApiError(RuntimeError):
    pass


class GraphVisApiClient:
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=httpx.Timeout(config.request_timeout),
        )
        self.username: str | None = None
        self.token: str | None = None

    async def close(self) -> None:
        await self.client.aclose()

    async def health(self) -> dict[str, Any]:
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()

    async def authenticate(self) -> dict[str, Any]:
        if self.token:
            return {"username": self.username, "authenticated": True}

        run_fragment = re.sub(r"[^A-Za-z0-9._-]", "-", self.config.run_id)[:22]
        self.username = f"eval-{run_fragment}-{secrets.token_hex(4)}"[:50]
        password = f"Eval-{secrets.token_urlsafe(18)}"
        response = await self.client.post(
            "/auth/register",
            json={"username": self.username, "password": password},
        )
        if response.status_code >= 400:
            detail = f"{response.status_code} {response.text}"
            raise GraphVisApiError(f"Could not create evaluation user: {detail}")
        payload = response.json()
        self.token = payload["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
        return {"username": self.username, "authenticated": True}

    def resolve_dataset(self, dataset: str) -> Path:
        candidate = Path(dataset).expanduser()
        if not candidate.is_absolute():
            candidate = self.config.repo_root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(self.config.repo_root)
        except ValueError as exc:
            raise GraphVisApiError(
                "Dataset must be inside the GraphVisAgent repository."
            ) from exc
        if not candidate.is_file():
            raise GraphVisApiError(f"Dataset does not exist: {candidate}")
        if candidate.suffix.lower() not in {".graphml", ".xml"}:
            raise GraphVisApiError("Dataset must be a GraphML or XML file.")
        return candidate

    async def _messages(self, chat_id: int) -> list[dict[str, Any]]:
        response = await self.client.get(f"/chat/{chat_id}/messages")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    async def _chat(self, chat_id: int) -> dict[str, Any]:
        response = await self.client.get(f"/chat/{chat_id}")
        response.raise_for_status()
        return response.json()

    async def _network_snapshot(
        self, network_id: int, render: dict[str, Any]
    ) -> dict[str, Any]:
        base = f"{self.config.networkx_api_url}/api/v1/networks/{network_id}"
        paths = {
            "metadata": f"{base}/metadata",
            "node_attributes": f"{base}/attributes/nodes",
            "edge_attributes": f"{base}/attributes/edges",
        }
        results: dict[str, Any] = {}
        warnings: list[str] = []
        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            responses = await asyncio.gather(
                *(client.get(url) for url in paths.values()),
                return_exceptions=True,
            )
        for (name, _url), response in zip(paths.items(), responses, strict=True):
            empty: Any = [] if name.endswith("attributes") else {}
            if isinstance(response, Exception):
                warnings.append(f"{name}: {type(response).__name__}: {response}")
                results[name] = empty
            elif response.is_success:
                results[name] = response.json()
            else:
                warnings.append(f"{name}: HTTP {response.status_code}")
                results[name] = empty
        return {
            "network_id": network_id,
            "render": render,
            **results,
            "inspection_warnings": warnings,
        }

    async def _wait_for_model_message(
        self,
        chat_id: int,
        known_model_ids: set[int],
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.turn_timeout
        last_messages: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            last_messages = await self._messages(chat_id)
            candidates = [
                message
                for message in last_messages
                if message.get("role") == "model"
                and message.get("id") not in known_model_ids
            ]
            if candidates:
                return candidates[-1]
            await asyncio.sleep(0.5)
        raise GraphVisApiError(
            f"Timed out after {self.config.turn_timeout:.0f}s "
            f"waiting for chat {chat_id}. "
            f"Observed {len(last_messages)} messages."
        )

    async def start_chat(self, dataset: str) -> StartedChat:
        await self.authenticate()
        dataset_path = self.resolve_dataset(dataset)
        response = await self.client.post(
            "/chat",
            json={
                "name": f"Evaluation {self.config.run_id}",
                "provider": "lmstudio",
                "model": self.config.model_id,
            },
        )
        response.raise_for_status()
        chat = response.json()
        chat_id = int(chat["id"])
        before = await self._messages(chat_id)
        known = {
            int(message["id"]) for message in before if message.get("role") == "model"
        }

        with dataset_path.open("rb") as handle:
            upload = await self.client.post(
                f"/chat/{chat_id}/upload",
                files={"file": (dataset_path.name, handle, "application/xml")},
                timeout=httpx.Timeout(self.config.request_timeout),
            )
        upload.raise_for_status()
        await self._wait_for_model_message(chat_id, known)
        hydrated = await self._chat(chat_id)
        render = (
            hydrated.get("network") if isinstance(hydrated.get("network"), dict) else {}
        )
        network_id = int(hydrated["network_id"])
        state = await self._network_snapshot(network_id, render)
        return StartedChat(
            chat_id=chat_id,
            network_id=network_id,
            initial_state=state,
        )

    async def send_message(
        self,
        chat_id: int,
        message: str,
        before_state: dict[str, Any],
    ) -> dict[str, Any]:
        messages_before = await self._messages(chat_id)
        known = {
            int(item["id"])
            for item in messages_before
            if item.get("role") == "model" and item.get("id") is not None
        }
        response = await self.client.post(
            f"/chat/{chat_id}/process",
            json={"message": {"content": message}},
        )
        response.raise_for_status()
        assistant = await self._wait_for_model_message(chat_id, known)
        chat = await self._chat(chat_id)
        render = chat.get("network") if isinstance(chat.get("network"), dict) else {}
        network_id = int(chat["network_id"])
        after_state = await self._network_snapshot(network_id, render)
        executions = assistant.get("tool_executions") or []
        skills = []
        tools = []
        for execution in executions:
            name = execution.get("tool_name")
            if not name:
                continue
            tools.append(name)
            if name == "skill_load":
                arguments = execution.get("arguments") or {}
                skill_name = arguments.get("name")
                if skill_name:
                    skills.append(str(skill_name))

        usage = assistant.get("usage") or {}
        return {
            "chat_id": chat_id,
            "network_id": network_id,
            "user_message": message,
            "assistant_message": assistant.get("content", ""),
            "skills_loaded": skills,
            "tools_called": tools,
            "tool_executions": _compact(executions),
            "visualization": summarize_visualization(after_state),
            "visualization_diff": diff_visualizations(before_state, after_state),
            "visualization_state": after_state,
            "provider": usage.get("provider") or chat.get("provider") or "lmstudio",
            "model": usage.get("model") or chat.get("model") or self.config.model_id,
        }

    async def observe(self, chat_id: int) -> dict[str, Any]:
        messages = await self._messages(chat_id)
        chat = await self._chat(chat_id)
        render = chat.get("network") if isinstance(chat.get("network"), dict) else {}
        network_id = int(chat["network_id"])
        state = await self._network_snapshot(network_id, render)
        return {
            "chat_id": chat_id,
            "network_id": network_id,
            "provider": chat.get("provider"),
            "model": chat.get("model"),
            "messages": _compact(messages),
            "visualization": summarize_visualization(state),
            "visualization_state": state,
        }

    async def lm_studio_model(self) -> dict[str, Any]:
        headers = {}
        # The API normally has no authentication. The environment variable is
        # supported for installations that enabled LM Studio auth.
        api_token = os.getenv("LM_STUDIO_API_KEY", "").strip()
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
            response = await client.get(
                f"{self.config.lm_studio_url}/api/v1/models", headers=headers
            )
            response.raise_for_status()
            models = response.json().get("models", [])
        match = next(
            (
                model
                for model in models
                if self.config.model_id
                in {model.get("key"), model.get("id"), model.get("model")}
            ),
            None,
        )
        return {
            "requested_model": self.config.model_id,
            "available": match is not None,
            "model": _compact(match) if match else None,
        }
