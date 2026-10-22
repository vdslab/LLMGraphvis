#!/usr/bin/env python3
"""Summarize agent turn traces (ADR 0032) as a Markdown report.

    python scripts/analyze_turns.py                       # every trace file
    python scripts/analyze_turns.py --since 2026-10-19T13:00 --chat 12
    python scripts/analyze_turns.py --dir backend/logs/turns --out report.md

Reads `backend/logs/turns/*.jsonl` by default. Unknown events and fields are
ignored, so the report keeps working as the trace grows. Standard library only.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "backend" / "logs" / "turns"
PREPARATION = {"skill_load", "tool_search"}
CONVERSATIONAL = {"ask_user", "offer_parameter_tuning", "apply_parameter_tuning"}


def load_turns(directory, since=None, chat=None):
    turns = defaultdict(list)
    for path in sorted(Path(directory).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            turns[event.get("turn_id")].append(event)
    result = []
    for events in turns.values():
        events.sort(key=lambda e: e.get("seq", 0))
        start = events[0]
        if since and start.get("ts", "") < since:
            continue
        if chat is not None and start.get("chat_id") != chat:
            continue
        result.append(events)
    result.sort(key=lambda evs: evs[0].get("ts", ""))
    return result


def _first(events, kind):
    return next((e for e in events if e.get("event") == kind), {})


def _all(events, kind):
    return [e for e in events if e.get("event") == kind]


def summarize_turn(events):
    start = _first(events, "turn_start")
    end = _first(events, "turn_end")
    tools = _all(events, "tool")
    generations = {
        g.get("iteration"): set(g.get("tools") or [])
        for g in _all(events, "generation")
    }

    # A call to a tool that the preceding generation did not offer: the model
    # guessed a name instead of discovering it.
    unexposed = []
    for call in tools:
        offered = generations.get((call.get("iteration") or 1) - 1)
        if offered is not None and call.get("name") not in offered:
            unexposed.append(call.get("name"))

    # Recovery: a denied/failed call later followed, in the same turn, by a
    # completed call of the same tool.
    recovered, unrecovered = [], []
    for i, call in enumerate(tools):
        if call.get("status") in {"failed", "deferred"}:
            later = [c for c in tools[i + 1 :] if c.get("name") == call.get("name")]
            (
                recovered
                if any(c.get("status") == "completed" for c in later)
                else unrecovered
            ).append(call.get("name"))

    first_skill = next(
        (i for i, c in enumerate(tools) if c.get("name") == "skill_load"), None
    )
    first_action = next(
        (
            i
            for i, c in enumerate(tools)
            if c.get("name") not in PREPARATION | CONVERSATIONAL
        ),
        None,
    )
    acted_before_skill = first_action is not None and (
        first_skill is None or first_action < first_skill
    )

    suggested = set(start.get("skills_suggested") or end.get("skills_suggested") or [])
    loaded = set(end.get("skills_loaded") or [])
    if not loaded:
        loaded = {
            (c.get("args") or {}).get("name")
            for c in tools
            if c.get("name") == "skill_load" and c.get("status") == "completed"
        } - {None}

    return {
        "turn_id": start.get("turn_id") or events[0].get("turn_id"),
        "ts": events[0].get("ts"),
        "chat_id": events[0].get("chat_id"),
        "model": start.get("model"),
        "user_text": start.get("user_text") or "",
        "resumed": bool(start.get("resumed_from_input")),
        "iterations": end.get("iteration") or len(_all(events, "model_response")),
        "max_iterations": end.get("max_iterations"),
        "tools": tools,
        "suggested": suggested,
        "loaded": loaded,
        "continuations": [c.get("requested_by") for c in _all(events, "continuation")],
        "asked_user": bool(end.get("asked_user")),
        "aborted": bool(end.get("should_abort")),
        "abort_reason": end.get("abort_reason"),
        "error": end.get("error"),
        "final_text": end.get("final_text") or "",
        "usage": end.get("usage") or {},
        "elapsed_ms": end.get("elapsed_ms"),
        "unexposed": unexposed,
        "recovered": recovered,
        "unrecovered": unrecovered,
        "acted_before_skill": acted_before_skill,
        "searches": [
            (c.get("args") or {}).get("query")
            for c in tools
            if c.get("name") == "tool_search"
        ],
        "complete": bool(end),
    }


_MARK = {"completed": "", "failed": "✗", "deferred": "⏸"}


def _tool_sequence(turn):
    parts = []
    for call in turn["tools"]:
        name = call.get("name")
        if name == "skill_load":
            name = f"skill_load({(call.get('args') or {}).get('name')})"
        mark = _MARK.get(call.get("status"), "?")
        if call.get("decision") == "modify":
            mark += "✎"
        parts.append(f"{name}{mark}")
    return " → ".join(parts) or "(none)"


def _cell(text, limit=60):
    text = " ".join(str(text).split())
    text = text if len(text) <= limit else text[: limit - 1] + "…"
    return text.replace("|", "\\|")


def render(turns):
    out = ["# Agent turn trace report", ""]
    if not turns:
        return "\n".join(out + ["No turns found."])

    summaries = [summarize_turn(t) for t in turns]
    models = Counter(s["model"] for s in summaries)
    iterations = [s["iterations"] or 0 for s in summaries]
    out += [
        f"- Turns: **{len(summaries)}** ({', '.join(f'{m}: {n}' for m, n in models.items())})",
        f"- Period: {summaries[0]['ts']} – {summaries[-1]['ts']}",
        f"- Iterations per turn: mean {mean(iterations):.1f}, median {median(iterations)}, max {max(iterations)}",
        f"- Turns that asked the user: {sum(s['asked_user'] for s in summaries)}",
        f"- Turns with a continuation nudge: {sum(bool(s['continuations']) for s in summaries)}",
        f"- Aborted turns: {sum(s['aborted'] for s in summaries)}; errored: {sum(bool(s['error']) for s in summaries)}; "
        f"incomplete traces: {sum(not s['complete'] for s in summaries)}",
        f"- Tokens: input {sum(s['usage'].get('input_tokens', 0) for s in summaries):,}, "
        f"output {sum(s['usage'].get('output_tokens', 0) for s in summaries):,}",
        "",
    ]

    # --- Per turn ---
    out += [
        "## Turns",
        "",
        "✗ failed/denied, ⏸ deferred, ✎ arguments modified by a hook.",
        "",
        "| # | chat | user | iter | tools | skills suggested → loaded | s |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(summaries, 1):
        flags = []
        if s["resumed"]:
            flags.append("resumed")
        if s["asked_user"]:
            flags.append("asked")
        if s["continuations"]:
            flags.append(f"nudged×{len(s['continuations'])}")
        if s["aborted"]:
            flags.append("ABORT")
        if s["error"]:
            flags.append("ERROR")
        if s["elapsed_ms"]:
            flags.append(f"{s['elapsed_ms'] / 1000:.0f}s")
        skills = f"{', '.join(sorted(s['suggested'])) or '–'} → {', '.join(sorted(s['loaded'])) or '–'}"
        out.append(
            f"| {i} | {s['chat_id']} | {_cell(s['user_text'], 50)} | {s['iterations']} | "
            f"{_cell(_tool_sequence(s), 400)} | {_cell(skills, 120)} | {' '.join(flags)} |"
        )
    out.append("")

    # --- Tools ---
    stats = defaultdict(Counter)
    durations = defaultdict(list)
    for s in summaries:
        for call in s["tools"]:
            stats[call.get("name")][call.get("status")] += 1
            if call.get("decision") == "modify":
                stats[call.get("name")]["modified"] += 1
            if (
                call.get("duration_ms") is not None
                and call.get("status") == "completed"
            ):
                durations[call.get("name")].append(call["duration_ms"])
    out += [
        "## Tool calls",
        "",
        "| tool | calls | completed | failed | deferred | modified | median ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, c in sorted(
        stats.items(),
        key=lambda kv: -sum(v for k, v in kv[1].items() if k != "modified"),
    ):
        total = c["completed"] + c["failed"] + c["deferred"]
        med = f"{median(durations[name]):.0f}" if durations[name] else "–"
        out.append(
            f"| {name} | {total} | {c['completed']} | {c['failed']} | {c['deferred']} | {c['modified']} | {med} |"
        )
    out.append("")

    # --- Hook decisions ---
    decisions = Counter()
    reasons = defaultdict(list)
    for s in summaries:
        for call in s["tools"]:
            if call.get("decision") in {"deny", "defer", "modify"}:
                key = (call.get("decided_by"), call.get("decision"), call.get("name"))
                decisions[key] += 1
                if call.get("reason"):
                    reasons[key].append(call["reason"])
    failures = Counter()
    for s in summaries:
        for call in s["tools"]:
            if call.get("status") == "failed" and call.get("decision") not in {"deny"}:
                failures[(call.get("name"), _cell(call.get("error") or "", 100))] += 1
    out += ["## Hook decisions", ""]
    if decisions:
        out += [
            "| hook | decision | tool | n | example reason |",
            "|---|---|---|---|---|",
        ]
        for (hook, decision, tool), n in decisions.most_common():
            example = (
                _cell(reasons[(hook, decision, tool)][0], 120)
                if reasons[(hook, decision, tool)]
                else ""
            )
            out.append(f"| {hook} | {decision} | {tool} | {n} | {example} |")
    else:
        out.append("No call was denied, deferred or modified.")
    out += ["", "## Tool errors (not hook denials)", ""]
    if failures:
        out += ["| tool | error | n |", "|---|---|---|"]
        for (tool, error), n in failures.most_common():
            out.append(f"| {tool} | {error} | {n} |")
    else:
        out.append("None.")
    out.append("")

    # --- Recovery ---
    recovered = sum(len(s["recovered"]) for s in summaries)
    unrecovered = Counter(name for s in summaries for name in s["unrecovered"])
    out += [
        "## Self-correction",
        "",
        f"- Failed/deferred calls later completed in the same turn: **{recovered}**",
        f"- Never recovered within the turn: **{sum(unrecovered.values())}**"
        + (
            f" ({', '.join(f'{k}×{v}' for k, v in unrecovered.most_common())})"
            if unrecovered
            else ""
        ),
        f"- Calls to a tool the previous generation did not offer: "
        f"**{sum(len(s['unexposed']) for s in summaries)}**"
        + (
            f" ({', '.join(sorted({n for s in summaries for n in s['unexposed']}))})"
            if any(s["unexposed"] for s in summaries)
            else ""
        ),
        "",
    ]

    # --- Skills ---
    suggested_total = Counter()
    hit = Counter()
    missed = Counter()
    unsuggested = Counter()
    for s in summaries:
        for name in s["suggested"]:
            suggested_total[name] += 1
            (hit if name in s["loaded"] else missed)[name] += 1
        for name in s["loaded"] - s["suggested"]:
            unsuggested[name] += 1
    acting = [
        s
        for s in summaries
        if any(c.get("name") not in PREPARATION | CONVERSATIONAL for c in s["tools"])
    ]
    out += [
        "## Skills",
        "",
        f"- Turns that ran a graph tool: {len(acting)}; of those, acted before any `skill_load`: "
        f"**{sum(s['acted_before_skill'] for s in acting)}**",
        f"- Turns that loaded no skill but ran a graph tool: **{sum(not s['loaded'] for s in acting)}**",
        "",
        "| skill | suggested | loaded when suggested | not loaded when suggested | loaded unsuggested |",
        "|---|---|---|---|---|",
    ]
    for name in sorted(set(suggested_total) | set(unsuggested)):
        out.append(
            f"| {name} | {suggested_total[name]} | {hit[name]} | {missed[name]} | {unsuggested[name]} |"
        )
    searches = [q for s in summaries for q in s["searches"] if q]
    if searches:
        out += [
            "",
            "`tool_search` queries: "
            + ", ".join(f"`{_cell(q, 40)}`" for q in searches),
        ]
    out.append("")

    # --- Endings ---
    out += ["## Final responses", ""]
    for i, s in enumerate(summaries, 1):
        ending = s["error"] or s["final_text"] or "(empty)"
        out.append(f"{i}. **{_cell(s['user_text'], 60)}** → {_cell(ending, 240)}")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="trace directory")
    parser.add_argument(
        "--since", help="ISO timestamp (UTC) lower bound, e.g. 2026-10-19T13:00"
    )
    parser.add_argument("--chat", type=int, help="only this chat id")
    parser.add_argument("--out", help="write the report here instead of stdout")
    args = parser.parse_args(argv)

    report = render(load_turns(args.dir, since=args.since, chat=args.chat))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
