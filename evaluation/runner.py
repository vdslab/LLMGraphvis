from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REQUIRED_MODEL = "google/gemma-4-e4b"
EVALUATION_SERVER = "graphvis-evaluation"
EVALUATION_TOOLS = [
    "list_prompt_surfaces",
    "read_prompt_surface",
    "start_test",
    "send_message",
    "observe_session",
    "reset_test",
    "finish_evaluation",
]


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.graphvis-evaluation.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


@contextlib.contextmanager
def temporary_cline_configuration(
    python: Path,
    environment: dict[str, str],
) -> Iterator[dict[str, Any]]:
    settings_root = Path.home() / ".cline" / "data" / "settings"
    providers_path = settings_root / "providers.json"
    mcp_path = settings_root / "cline_mcp_settings.json"
    if not providers_path.is_file() or not mcp_path.is_file():
        raise RuntimeError(
            "Cline settings were not found. Configure Cline and the "
            "LM Studio provider first."
        )

    originals = {path: path.read_bytes() for path in (providers_path, mcp_path)}
    providers = json.loads(originals[providers_path])
    lmstudio = providers.get("providers", {}).get("lmstudio", {})
    configured_model = lmstudio.get("settings", {}).get("model")
    if configured_model != REQUIRED_MODEL:
        raise RuntimeError(
            "Cline's LM Studio provider must be configured with exactly "
            f"{REQUIRED_MODEL!r}; found {configured_model!r}."
        )

    mcp_settings = json.loads(originals[mcp_path])
    servers = mcp_settings.setdefault("mcpServers", {})
    for name, server in servers.items():
        if name != EVALUATION_SERVER and isinstance(server, dict):
            server["disabled"] = True
    servers[EVALUATION_SERVER] = {
        "type": "stdio",
        "command": str(python),
        "args": ["-m", "evaluation.server"],
        "env": environment,
        "timeout": 900,
        "disabled": False,
        "autoApprove": EVALUATION_TOOLS,
    }
    providers["lastUsedProvider"] = "lmstudio"

    try:
        _atomic_json(providers_path, providers)
        _atomic_json(mcp_path, mcp_settings)
        yield {
            "provider": "lmstudio",
            "model": configured_model,
            "mcp_server": EVALUATION_SERVER,
        }
    finally:
        for path, content in originals.items():
            temporary = path.with_name(f".{path.name}.graphvis-evaluation.restore")
            temporary.write_bytes(content)
            os.replace(temporary, path)


def _wait_http(url: str, name: str, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # pragma: no cover - depends on local services
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"{name} did not become ready at {url}: {last_error}")


def _model_preflight(url: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{url.rstrip('/')}/api/v1/models")
    api_key = os.getenv("LM_STUDIO_API_KEY", "").strip()
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    models = payload.get("models", [])
    matched = next(
        (
            item
            for item in models
            if REQUIRED_MODEL in {item.get("key"), item.get("id"), item.get("model")}
        ),
        None,
    )
    if matched is None:
        raise RuntimeError(
            "LM Studio is reachable but does not report the required model "
            f"{REQUIRED_MODEL!r}."
        )
    return {"requested_model": REQUIRED_MODEL, "model": matched}


def _compose(
    root: Path,
    project: str,
    args: list[str],
    environment: dict[str, str],
) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(root / "docker-compose.evaluation.yml"),
            "-p",
            project,
            *args,
        ],
        cwd=root,
        env=environment,
        check=True,
    )


def _stream_cline(command: list[str], cwd: Path, log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            return process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise


def _prompt(root: Path, target: str, dataset: str, max_probes: int, run_id: str) -> str:
    template = (root / "evaluation" / "CLINE_EVALUATOR.md").read_text(encoding="utf-8")
    return template.format(
        target=target,
        dataset=dataset,
        max_probes=max_probes,
        run_id=run_id,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a free-form Cline evaluation of GraphVisAgent prompt surfaces."
    )
    parser.add_argument(
        "--target", required=True, help="Evaluation objective for Cline."
    )
    parser.add_argument(
        "--dataset",
        default="sample_data/davis_southern_women.graphml",
        help="GraphML/XML path inside this repository.",
    )
    parser.add_argument("--max-probes", type=int, default=10)
    parser.add_argument(
        "--existing-stack",
        action="store_true",
        help=(
            "Use backend :8000, NetworkX :8001, and frontend :5173 "
            "instead of Docker isolation."
        ),
    )
    parser.add_argument(
        "--keep-stack",
        action="store_true",
        help="Leave the isolated Docker stack running after evaluation.",
    )
    parser.add_argument("--cline", default=shutil.which("cline") or "cline")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.max_probes <= 50:
        raise SystemExit("--max-probes must be between 1 and 50")

    root = _root()
    dataset_path = (
        (root / args.dataset).resolve()
        if not Path(args.dataset).is_absolute()
        else Path(args.dataset).resolve()
    )
    try:
        dataset = str(dataset_path.relative_to(root))
    except ValueError as exc:
        raise SystemExit(
            "--dataset must resolve inside the GraphVisAgent repository"
        ) from exc
    if not dataset_path.is_file():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    run_id = _run_id()
    run_dir = root / ".evaluation" / "runs" / run_id
    workspace = run_dir / "cline-workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    python = root / ".local" / "venv" / "bin" / "python"
    if not python.is_file():
        raise SystemExit(
            "Evaluation Python environment is missing. Run scripts/setup-evaluation."
        )

    isolated = not args.existing_stack
    api_url = "http://127.0.0.1:18000" if isolated else "http://127.0.0.1:8000"
    frontend_url = "http://127.0.0.1:15173" if isolated else "http://127.0.0.1:5173"
    nx_url = (
        "http://127.0.0.1:18001/mcp/sse"
        if isolated
        else "http://127.0.0.1:8001/mcp/sse"
    )
    lm_studio_url = os.getenv("GRAPHVIS_LM_STUDIO_URL", "http://127.0.0.1:1234")
    project = f"graphvis-eval-{re.sub(r'[^a-z0-9]', '', run_id.lower())}"
    child_env = os.environ.copy()
    child_env.update(
        {
            "GRAPHVIS_REPO_ROOT": str(root),
            "GRAPHVIS_API_URL": api_url,
            "GRAPHVIS_FRONTEND_URL": frontend_url,
            "GRAPHVIS_NX_MCP_URL": nx_url,
            "GRAPHVIS_LM_STUDIO_URL": lm_studio_url,
            "GRAPHVIS_EVAL_MODEL": REQUIRED_MODEL,
            "GRAPHVIS_EVAL_RUN_ID": run_id,
            "GRAPHVIS_EVAL_TARGET": args.target,
            "GRAPHVIS_EVAL_MAX_PROBES": str(args.max_probes),
            "GRAPHVIS_EVAL_ARTIFACT_ROOT": str(run_dir.parent),
            "PYTHONPATH": str(root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "EVALUATION_SECRET_KEY": os.getenv(
                "EVALUATION_SECRET_KEY", "evaluation-only-secret-key-change-me"
            ),
        }
    )
    mcp_env = {
        key: child_env[key]
        for key in (
            "GRAPHVIS_REPO_ROOT",
            "GRAPHVIS_API_URL",
            "GRAPHVIS_FRONTEND_URL",
            "GRAPHVIS_NX_MCP_URL",
            "GRAPHVIS_LM_STUDIO_URL",
            "GRAPHVIS_EVAL_MODEL",
            "GRAPHVIS_EVAL_RUN_ID",
            "GRAPHVIS_EVAL_TARGET",
            "GRAPHVIS_EVAL_MAX_PROBES",
            "GRAPHVIS_EVAL_ARTIFACT_ROOT",
            "PYTHONPATH",
            "PYTHONDONTWRITEBYTECODE",
        )
    }
    if child_env.get("LM_STUDIO_API_KEY"):
        mcp_env["LM_STUDIO_API_KEY"] = child_env["LM_STUDIO_API_KEY"]

    stack_started = False
    try:
        preflight = _model_preflight(lm_studio_url)
        if isolated:
            print("Starting isolated GraphVisAgent evaluation stack…", flush=True)
            stack_started = True
            _compose(root, project, ["up", "-d", "--build"], child_env)
        _wait_http(f"{api_url}/health", "GraphVisAgent backend")
        _wait_http(frontend_url, "GraphVisAgent frontend")
        _wait_http(nx_url.rsplit("/mcp/sse", 1)[0] + "/health", "NetworkX API")

        with temporary_cline_configuration(python, mcp_env) as cline_model:
            (run_dir / "model-preflight.json").write_text(
                json.dumps(
                    {"cline": cline_model, "lm_studio": preflight},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            prompt = _prompt(root, args.target, dataset, args.max_probes, run_id)
            (run_dir / "evaluator-instructions.md").write_text(prompt, encoding="utf-8")
            command = [
                args.cline,
                prompt,
                "--mode",
                "plan",
                "--oneshot",
                "--output-format",
                "plain",
                "--workspace",
                str(workspace),
            ]
            print(f"Running Cline with {REQUIRED_MODEL} (run {run_id})…", flush=True)
            return_code = _stream_cline(command, workspace, run_dir / "cline.log")
            if return_code:
                raise RuntimeError(f"Cline exited with status {return_code}")

        report = run_dir / "report.md"
        if not report.is_file():
            raise RuntimeError("Cline finished without calling finish_evaluation.")
        print(f"Evaluation report: {report}")
        print(f"JSON report: {run_dir / 'report.json'}")
        return 0
    finally:
        if stack_started and not args.keep_stack:
            print("Stopping isolated evaluation stack…", flush=True)
            _compose(
                root, project, ["down", "--volumes", "--remove-orphans"], child_env
            )


if __name__ == "__main__":
    raise SystemExit(main())
