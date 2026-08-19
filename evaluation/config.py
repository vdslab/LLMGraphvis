from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    configured = os.getenv("GRAPHVIS_REPO_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EvaluationConfig:
    repo_root: Path
    api_url: str
    frontend_url: str
    networkx_mcp_url: str
    lm_studio_url: str
    model_id: str
    artifact_root: Path
    run_id: str
    request_timeout: float
    turn_timeout: float
    max_probes: int

    @classmethod
    def from_env(cls) -> "EvaluationConfig":
        root = _repo_root()
        artifact_root = Path(
            os.getenv("GRAPHVIS_EVAL_ARTIFACT_ROOT", root / ".evaluation" / "runs")
        ).expanduser()
        return cls(
            repo_root=root,
            api_url=os.getenv("GRAPHVIS_API_URL", "http://127.0.0.1:18000").rstrip("/"),
            frontend_url=os.getenv(
                "GRAPHVIS_FRONTEND_URL", "http://127.0.0.1:15173"
            ).rstrip("/"),
            networkx_mcp_url=os.getenv(
                "GRAPHVIS_NX_MCP_URL", "http://127.0.0.1:18001/mcp/sse"
            ),
            lm_studio_url=os.getenv(
                "GRAPHVIS_LM_STUDIO_URL", "http://127.0.0.1:1234"
            ).rstrip("/"),
            model_id=os.getenv("GRAPHVIS_EVAL_MODEL", "google/gemma-4-e4b"),
            artifact_root=artifact_root.resolve(),
            run_id=os.getenv("GRAPHVIS_EVAL_RUN_ID", "manual"),
            request_timeout=float(os.getenv("GRAPHVIS_EVAL_REQUEST_TIMEOUT", "30")),
            turn_timeout=float(os.getenv("GRAPHVIS_EVAL_TURN_TIMEOUT", "600")),
            max_probes=int(os.getenv("GRAPHVIS_EVAL_MAX_PROBES", "10")),
        )

    @property
    def run_dir(self) -> Path:
        return self.artifact_root / self.run_id

    @property
    def networkx_api_url(self) -> str:
        return self.networkx_mcp_url.split("/mcp/", 1)[0].rstrip("/")

    def ensure_directories(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "sessions").mkdir(exist_ok=True)
        (self.run_dir / "screenshots").mkdir(exist_ok=True)
