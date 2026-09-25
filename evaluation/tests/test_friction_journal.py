import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from evaluation.bridge import EvaluationBridge, EvaluationSession
from evaluation.config import EvaluationConfig


def _bridge(tmp_path):
    config = replace(
        EvaluationConfig.from_env(), artifact_root=tmp_path, run_id="friction-test"
    )
    bridge = EvaluationBridge(config)
    bridge.sessions["session-1"] = EvaluationSession(
        session_id="session-1",
        dataset="sample.graphml",
        chat_id=1,
        network_id=1,
        current_state={},
        probe_count=1,
        observations=[{"probe_number": 1, "assistant_message": "Done"}],
    )
    return bridge


def test_records_evaluator_confusion_for_observed_probe(tmp_path):
    bridge = _bridge(tmp_path)
    note = bridge.record_analysis_friction(
        "session-1",
        1,
        "parameter choice",
        "Why was resolution changed?",
        ["The reply named no previous value."],
        "skill",
        "parameter-tuning",
        "Explain the value change.",
    )

    assert note["note_id"] == "FN-001"
    assert note["suspected_surface"] == "skill"
    journal = json.loads((bridge.config.run_dir / "friction.json").read_text())
    assert journal == [note]
    session = json.loads(
        (bridge.config.run_dir / "sessions" / "session-1.json").read_text()
    )
    assert session["friction_notes"] == [note]


def test_rejects_notes_without_an_observed_probe_or_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    with pytest.raises(ValueError, match="was not observed"):
        bridge.record_analysis_friction("session-1", 2, "result", "Unclear", ["Seen"])
    with pytest.raises(ValidationError):
        bridge.record_analysis_friction("session-1", 1, "result", "Unclear", [])
    assert not (bridge.config.run_dir / "friction.json").exists()
