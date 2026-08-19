import json

from evaluation.reports import save_report


def test_report_writes_json_and_markdown(tmp_path) -> None:
    report, json_path, markdown_path = save_report(
        tmp_path,
        "run-1",
        {
            "target": "skill discovery",
            "evaluator_model": "google/gemma-4-e4b",
            "graphvis_model": "google/gemma-4-e4b",
            "summary": "One probe succeeded.",
            "trials": [
                {
                    "session_id": "session-1",
                    "probe_number": 1,
                    "user_message": "Color nodes by group.",
                    "assistant_message": "Done.",
                    "skills_loaded": ["visual-encoding"],
                    "tools_called": ["skill_load"],
                    "model": "google/gemma-4-e4b",
                    "capture": {"path": "screenshots/probe-01.png"},
                }
            ],
            "findings": [
                {
                    "finding_id": "F-001",
                    "probe_number": 1,
                    "severity": "info",
                    "hypothesis": "The Skill is discoverable.",
                    "test_prompt": "Color nodes by group.",
                    "expected_behavior": "Load the Skill.",
                    "failure_condition": "The Skill is not loaded.",
                    "actual_response": "Done.",
                    "observed_skills": ["visual-encoding"],
                    "observed_tools": ["skill_load"],
                    "visualization_evidence": ["screenshots/probe-01.png"],
                    "verdict": "success",
                    "cause_category": "none",
                }
            ],
        },
    )

    assert report.findings[0].verdict == "success"
    assert json.loads(json_path.read_text())["findings"][0]["finding_id"] == "F-001"
    markdown = markdown_path.read_text()
    assert "F-001" in markdown
    assert "Probe 1" in markdown
    assert "google/gemma-4-e4b" in markdown
