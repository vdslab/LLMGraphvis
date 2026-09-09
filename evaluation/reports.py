from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    finding_id: str = Field(min_length=1)
    probe_number: int = Field(ge=1)
    severity: Literal["critical", "high", "medium", "low", "info"]
    hypothesis: str
    test_prompt: str
    expected_behavior: str
    failure_condition: str
    actual_response: str
    observed_skills: list[str] = Field(default_factory=list)
    observed_tools: list[str] = Field(default_factory=list)
    visualization_evidence: list[str] = Field(default_factory=list)
    verdict: Literal["success", "partial", "failure", "not_evaluable"]
    cause_category: Literal[
        "system_prompt",
        "skill",
        "mcp_description",
        "implementation",
        "frontend",
        "model_variability",
        "environment",
        "none",
    ]
    prompt_surface: str = ""
    current_wording: str = ""
    recommended_wording: str = ""
    rationale: str = ""
    possible_side_effects: str = ""
    follow_up_example: str = ""


class EvaluationReport(BaseModel):
    target: str
    evaluator_model: str
    graphvis_model: str
    summary: str
    trials: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    implementation_issues: list[str] = Field(default_factory=list)
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def render_markdown(report: EvaluationReport, run_id: str) -> str:
    lines = [
        "# GraphVisAgent prompt evaluation",
        "",
        f"- Run: `{run_id}`",
        f"- Target: {report.target}",
        f"- Evaluator model: `{report.evaluator_model}`",
        f"- GraphVisAgent model: `{report.graphvis_model}`",
        f"- Completed: {report.completed_at}",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        "## Trial log",
        "",
    ]
    if not report.trials:
        lines.extend(["No probes were recorded.", ""])
    for trial in report.trials:
        capture = trial.get("capture") or {}
        lines.extend(
            [
                f"### Probe {trial.get('probe_number', '?')}",
                "",
                f"- Session: `{trial.get('session_id', 'unknown')}`",
                f"- Prompt: {trial.get('user_message', '')}",
                f"- Skills: {', '.join(trial.get('skills_loaded', [])) or 'none'}",
                f"- Tools: {', '.join(trial.get('tools_called', [])) or 'none'}",
                f"- Model: `{trial.get('model', 'unknown')}`",
                f"- PNG: `{capture.get('path') or 'not captured'}`",
                "",
                "Response:",
                "",
                trial.get("assistant_message", "") or "(empty)",
                "",
            ]
        )

    lines.extend(
        [
            "## Findings",
            "",
        ]
    )
    if not report.findings:
        lines.extend(["No findings were recorded.", ""])

    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.finding_id}: {finding.verdict} ({finding.severity})",
                "",
                f"- Cause: `{finding.cause_category}`",
                f"- Probe: {finding.probe_number}",
                f"- Prompt surface: `{finding.prompt_surface or 'n/a'}`",
                f"- Hypothesis: {finding.hypothesis}",
                f"- Test prompt: {finding.test_prompt}",
                f"- Expected: {finding.expected_behavior}",
                f"- Failure condition: {finding.failure_condition}",
                f"- Observed skills: {', '.join(finding.observed_skills) or 'none'}",
                f"- Observed tools: {', '.join(finding.observed_tools) or 'none'}",
                "",
                "#### Actual response",
                "",
                finding.actual_response or "(empty)",
                "",
            ]
        )
        if finding.visualization_evidence:
            lines.extend(
                [
                    "#### Evidence",
                    "",
                    *[f"- `{path}`" for path in finding.visualization_evidence],
                    "",
                ]
            )
        if finding.current_wording or finding.recommended_wording:
            lines.extend(
                [
                    "#### Recommended prompt-surface change",
                    "",
                    f"Current wording: {finding.current_wording or '(not specified)'}",
                    "",
                    "Recommended wording: "
                    f"{finding.recommended_wording or '(not specified)'}",
                    "",
                    f"Rationale: {finding.rationale or '(not specified)'}",
                    "",
                    "Possible side effects: "
                    f"{finding.possible_side_effects or 'none identified'}",
                    "",
                    "Follow-up example: "
                    f"{finding.follow_up_example or '(not specified)'}",
                    "",
                ]
            )

    lines.extend(["## Implementation issues", ""])
    if report.implementation_issues:
        lines.extend(f"- {issue}" for issue in report.implementation_issues)
    else:
        lines.append(
            "None recorded. Prompt-surface findings are kept separate "
            "from code defects."
        )
    lines.append("")
    return "\n".join(lines)


def save_report(
    run_dir: Path,
    run_id: str,
    payload: dict[str, Any],
) -> tuple[EvaluationReport, Path, Path]:
    report = EvaluationReport.model_validate(payload)
    json_path = run_dir / "report.json"
    markdown_path = run_dir / "report.md"
    json_path.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report, run_id), encoding="utf-8")
    return report, json_path, markdown_path
