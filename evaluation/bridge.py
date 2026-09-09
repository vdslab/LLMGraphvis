from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .api import GraphVisApiClient
from .capture import capture_graph
from .config import EvaluationConfig
from .visualization import diff_visualizations, summarize_visualization


@dataclass
class EvaluationSession:
    session_id: str
    dataset: str
    chat_id: int
    network_id: int
    current_state: dict[str, Any]
    probe_count: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)


class EvaluationBridge:
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.config.ensure_directories()
        self.api = GraphVisApiClient(config)
        self.sessions: dict[str, EvaluationSession] = {}

    async def start(self, dataset: str) -> dict[str, Any]:
        model = await self.api.lm_studio_model()
        if not model["available"]:
            requested = self.config.model_id
            raise RuntimeError(
                f"LM Studio does not report the required model {requested!r}."
            )
        started = await self.api.start_chat(dataset)
        session_id = f"session-{secrets.token_hex(5)}"
        session = EvaluationSession(
            session_id=session_id,
            dataset=str(self.api.resolve_dataset(dataset)),
            chat_id=started.chat_id,
            network_id=started.network_id,
            current_state=started.initial_state,
        )
        self.sessions[session_id] = session
        self._save_session(session)
        return {
            "session_id": session_id,
            "chat_id": session.chat_id,
            "network_id": session.network_id,
            "dataset": session.dataset,
            "graphvis_provider": "lmstudio",
            "graphvis_model": self.config.model_id,
            "lm_studio_preflight": model,
            "instruction": (
                "Before each send_message call, state your hypothesis, "
                "expected behavior, "
                "and failure condition in your own evaluation notes."
            ),
        }

    async def send(
        self,
        session_id: str,
        message: str,
        capture: bool,
    ) -> tuple[dict[str, Any], Path | None]:
        session = self._get(session_id)
        probes_used = sum(item.probe_count for item in self.sessions.values())
        if probes_used >= self.config.max_probes:
            raise ValueError(
                f"This run is limited to {self.config.max_probes} probes. "
                "Finish the evaluation using the evidence already collected."
            )
        global_probe_number = probes_used + 1
        session.probe_count += 1
        try:
            observation = await self.api.send_message(
                session.chat_id,
                message,
                session.current_state,
            )
            session.current_state = observation.pop("visualization_state")
        except Exception as exc:
            observation = {
                "chat_id": session.chat_id,
                "network_id": session.network_id,
                "user_message": message,
                "assistant_message": "",
                "skills_loaded": [],
                "tools_called": [],
                "tool_executions": [],
                "visualization": summarize_visualization(session.current_state),
                "visualization_diff": diff_visualizations(
                    session.current_state, session.current_state
                ),
                "provider": "lmstudio",
                "model": self.config.model_id,
                "turn_error": f"{type(exc).__name__}: {exc}",
            }
        screenshot_path: Path | None = None
        if capture:
            screenshot_path = (
                self.config.run_dir
                / "screenshots"
                / f"{session.session_id}-probe-{global_probe_number:02d}.png"
            )
            summary = observation["visualization"]
            capture_result = await capture_graph(
                self.config,
                session.chat_id,
                self.api.token or "",
                int(summary.get("node_count", 0)),
                int(summary.get("link_count", 0)),
                screenshot_path,
            )
            observation["capture"] = capture_result
            if not capture_result.get("captured"):
                screenshot_path = None
        else:
            observation["capture"] = {"captured": False, "reason": "capture disabled"}

        observation["probe_number"] = global_probe_number
        session.observations.append(observation)
        self._save_session(session)
        return observation, screenshot_path

    async def observe(self, session_id: str) -> tuple[dict[str, Any], Path | None]:
        session = self._get(session_id)
        observation = await self.api.observe(session.chat_id)
        state = observation.pop("visualization_state")
        session.current_state = state
        screenshot_path = (
            self.config.run_dir / "screenshots" / f"{session.session_id}-current.png"
        )
        summary = observation["visualization"]
        capture_result = await capture_graph(
            self.config,
            session.chat_id,
            self.api.token or "",
            int(summary.get("node_count", 0)),
            int(summary.get("link_count", 0)),
            screenshot_path,
        )
        observation["capture"] = capture_result
        if not capture_result.get("captured"):
            screenshot_path = None
        self._save_session(session)
        return observation, screenshot_path

    async def reset(self, session_id: str) -> dict[str, Any]:
        session = self._get(session_id)
        started = await self.api.start_chat(session.dataset)
        session.chat_id = started.chat_id
        session.network_id = started.network_id
        session.current_state = started.initial_state
        self._save_session(session)
        return {
            "session_id": session.session_id,
            "chat_id": session.chat_id,
            "network_id": session.network_id,
            "dataset": session.dataset,
            "status": "reset",
        }

    def _get(self, session_id: str) -> EvaluationSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise ValueError(f"Unknown evaluation session: {session_id}") from exc

    def _save_session(self, session: EvaluationSession) -> None:
        path = self.config.run_dir / "sessions" / f"{session.session_id}.json"
        payload = {
            "session_id": session.session_id,
            "dataset": session.dataset,
            "chat_id": session.chat_id,
            "network_id": session.network_id,
            "probe_count": session.probe_count,
            "observations": session.observations,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
