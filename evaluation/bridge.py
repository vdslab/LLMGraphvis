from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .api import GraphVisApiClient
from .capture import capture_graph
from .config import EvaluationConfig
from .reports import FrictionNote
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
    friction_notes: list[dict[str, Any]] = field(default_factory=list)


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

    def record_analysis_friction(
        self,
        session_id: str,
        probe_number: int,
        where_in_workflow: str,
        unclear_point: str,
        evidence: list[str],
        suspected_surface: str = "unknown",
        surface_name: str = "",
        suggested_change: str = "",
    ) -> dict[str, Any]:
        """Persist an evaluator note against an observed probe.

        Record it before final synthesis.
        """
        session = self._get(session_id)
        if not any(
            item.get("probe_number") == probe_number for item in session.observations
        ):
            raise ValueError(
                f"Probe {probe_number} was not observed in session {session_id}."
            )
        next_number = 1 + sum(len(s.friction_notes) for s in self.sessions.values())
        note = FrictionNote.model_validate(
            {
                "note_id": f"FN-{next_number:03d}",
                "session_id": session_id,
                "probe_number": probe_number,
                "where_in_workflow": where_in_workflow.strip(),
                "unclear_point": unclear_point.strip(),
                "evidence": [item.strip() for item in evidence if item.strip()],
                "suspected_surface": suspected_surface,
                "surface_name": surface_name.strip(),
                "suggested_change": suggested_change.strip(),
            }
        ).model_dump()
        session.friction_notes.append(note)
        self._save_session(session)
        self._save_friction_journal()
        return note

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
            "friction_notes": session.friction_notes,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _save_friction_journal(self) -> None:
        path = self.config.run_dir / "friction.json"
        notes = [
            note
            for session in self.sessions.values()
            for note in session.friction_notes
        ]
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
