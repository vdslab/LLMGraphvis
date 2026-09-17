"""Parameter tuning sessions: one re-runnable pipeline, adjusted by words or a panel.

A session is built from calls that already ran successfully in the current turn
(their effective, hook-normalized arguments), plus 1–4 fields the model picked.
The agent (`apply_parameter_tuning`) and the panel (`POST .../apply`) both go
through `apply()`, so they share one state. See ADR 0016.
"""

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from common import models

from . import emitters, mcp_client
from .inputs import is_valid_number

OFFER_TOOL = "offer_parameter_tuning"
APPLY_TOOL = "apply_parameter_tuning"

# Re-running these keeps the user looking at the same network. `subgraph_*`
# would create a new network on every change and a view switch changes what is
# being looked at, so neither is "the same result with different parameters".
TUNABLE_PREFIXES = ("analysis_", "layout_", "visualization_")
UNTUNABLE_TOOLS = frozenset({"visualization_switch_network"})
MAX_HISTORY = 10


def is_tunable_tool(name: str) -> bool:
    return name.startswith(TUNABLE_PREFIXES) and name not in UNTUNABLE_TOOLS


class TuningError(ValueError):
    """A request the caller can correct (bad value, unknown parameter)."""


class TuningInactive(TuningError):
    """The panel was superseded, confirmed, or belongs to another network."""


class TuningExecutionError(RuntimeError):
    def __init__(self, tool: str, message: str):
        super().__init__(f"{tool} failed: {message}")
        self.tool = tool


def _load_json_string(value):
    """Models occasionally send an array argument as a JSON string."""
    if isinstance(value, str):
        match = re.search(r"(\[[\s\S]*\])", value)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return value
    return value


class TuningField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(
        min_length=1,
        max_length=80,
        description="Pipeline tool whose argument this row adjusts; must be listed in `tools`.",
    )
    argument: str = Field(
        pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$",
        description="Exact parameter key of that tool, e.g. 'resolution'.",
    )
    kind: Literal["slider", "number", "select"] = Field(
        description="slider for a numeric parameter with a sensible range (the usual "
        "case); number for an open-ended one; select for named choices."
    )
    minimum: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="Low end of the range worth exploring on this data, inside the "
        "tool's own bounds. Required for slider.",
    )
    maximum: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="High end of the range worth exploring. Required for slider.",
    )
    step: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description="Granularity. Whole numbers for integer parameters.",
    )
    options: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="select only: the values the parameter accepts.",
    )
    suggested: int | float | str | None = Field(
        default=None,
        description="Your recommended value for this data. The panel starts here; it "
        "is shown as a guide and NOT applied. Required when the tool ran with an "
        "automatic default (pass the reported effective value if you have no better one).",
    )
    rationale: str | None = Field(
        default=None,
        max_length=200,
        description="One sentence, in the conversation language, on why `suggested` "
        "fits this data.",
    )
    low_label: str | None = Field(
        default=None,
        max_length=40,
        description="What the low end does to the view, in the conversation language "
        "(e.g. 'larger groups').",
    )
    high_label: str | None = Field(
        default=None,
        max_length=40,
        description="What the high end does to the view (e.g. 'finer groups').",
    )

    @property
    def id(self) -> str:
        return f"{self.tool}.{self.argument}"

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, value):
        """Accept the short names models reach for (`min`, `max`, `default`).

        Seen with a local model that sent `min` twice and never recovered from
        the `extra_forbidden` error. Other unknown keys are still rejected.
        """
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for alias, name in (("min", "minimum"), ("max", "maximum"), ("default", "suggested")):
            if alias in normalized and normalized.get(name) is None:
                normalized[name] = normalized.pop(alias)
        return normalized

    @model_validator(mode="after")
    def check_controls(self):
        if self.kind == "select":
            if len(self.options) < 2:
                raise ValueError("select needs at least two options")
            if len(set(self.options)) != len(self.options):
                raise ValueError("options must be unique")
            if any(v is not None for v in (self.minimum, self.maximum, self.step)):
                raise ValueError("select takes options, not minimum/maximum/step")
            return self
        if self.options:
            raise ValueError("Only select fields take options")
        if self.kind == "slider" and (self.minimum is None or self.maximum is None):
            raise ValueError("slider requires minimum and maximum")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum >= self.maximum
        ):
            raise ValueError("minimum must be less than maximum")
        return self


class TuningForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(
        min_length=1,
        max_length=300,
        description="Short panel heading in the conversation language.",
    )
    tools: list[str] = Field(
        min_length=1,
        max_length=6,
        description="The pipeline re-run on every change, in order: the analysis or "
        "layout call, the encoding call that consumes its output, and "
        "visualization_generate when it was needed to draw. Each must already have "
        "run successfully on the current view (in this or an earlier turn); the "
        "arguments it last ran with become the base, so you do not repeat them.",
    )
    fields: list[TuningField] = Field(
        min_length=1,
        max_length=4,
        description="1-4 parameters that most change the result, most influential "
        "first. Parameters that are meaningful to move together (e.g. ForceAtlas2 "
        "scaling_ratio and gravity) belong in the same panel.",
    )

    @model_validator(mode="before")
    @classmethod
    def decode_string_arrays(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            for key in ("tools", "fields"):
                if key in value:
                    value[key] = _load_json_string(value[key])
        return value

    @model_validator(mode="after")
    def check_structure(self):
        if len(set(self.tools)) != len(self.tools):
            raise ValueError("tools must be unique")
        ids = [field.id for field in self.fields]
        if len(set(ids)) != len(ids):
            raise ValueError("Each tool.argument may appear once")
        for field in self.fields:
            if field.tool not in self.tools:
                raise ValueError(f"fields: '{field.tool}' is not listed in tools")
        return self


class ParameterChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    param: str = Field(
        pattern=r"^[a-z][a-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$",
        description="'<tool>.<argument>' of a pipeline tool, e.g. "
        "'analysis_louvain_communities.resolution'. Arguments that are not panel "
        "fields are accepted too.",
    )
    value: int | float | str | bool | None = Field(
        description="The new absolute value (already converted from any relative "
        "request such as 'a bit finer'). null restores the tool's automatic default."
    )


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[ParameterChange] = Field(
        min_length=1,
        max_length=10,
        description="Every change the request asks for, in ONE call; the pipeline "
        "re-runs once.",
    )
    tuning_id: str | None = Field(
        default=None,
        description="Panel to adjust. Omit for the active panel of the current view.",
    )

    @model_validator(mode="before")
    @classmethod
    def decode_string_array(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if "changes" in value:
                value["changes"] = _load_json_string(value["changes"])
        return value


# --- JSON schema helpers ----------------------------------------------------


def _schema_types(prop: dict) -> set[str]:
    types: set[str] = set()
    declared = prop.get("type")
    if isinstance(declared, str):
        types.add(declared)
    elif isinstance(declared, list):
        types.update(t for t in declared if isinstance(t, str))
    for key in ("anyOf", "oneOf"):
        for sub in prop.get(key) or []:
            if isinstance(sub, dict):
                types |= _schema_types(sub)
    return types - {"null"}


def _schema_value(prop: dict, key: str):
    if key in prop:
        return prop[key]
    for group in ("anyOf", "oneOf"):
        for sub in prop.get(group) or []:
            if isinstance(sub, dict) and key in sub:
                return sub[key]
    return None


def _properties(catalog, tool: str) -> dict:
    definition = catalog.get(tool) if catalog is not None else None
    if definition is None:
        raise TuningError(f"'{tool}' is not an available tool")
    return (definition.parameters or {}).get("properties") or {}


def _readable(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in detail['loc']) or '(root)'}: {detail['msg']}"
        for detail in error.errors()
    )


# --- values -----------------------------------------------------------------


def _format_bounds(spec: dict) -> str:
    text = f"{spec.get('minimum')}–{spec.get('maximum')}"
    if spec.get("step") is not None:
        text += f" (step {spec['step']})"
    return text


def coerce_value(spec: dict, value, *, label: str | None = None):
    """Validate one field value against the panel's own contract."""
    name = label or spec["id"]
    if spec["kind"] == "select":
        if value not in spec["options"]:
            raise TuningError(f"{name}: choose one of {spec['options']}")
        return value
    if spec.get("integer") and isinstance(value, float) and value.is_integer():
        value = int(value)
    if spec.get("integer") and (not isinstance(value, int) or isinstance(value, bool)):
        raise TuningError(f"{name} must be a whole number")
    if not is_valid_number(
        value, spec.get("minimum"), spec.get("maximum"), spec.get("step")
    ):
        raise TuningError(f"{name}={value!r} is outside {_format_bounds(spec)}")
    return value


def _is_payload(result) -> bool:
    return isinstance(result, dict) and "nodes" in result and "links" in result


def _summarize(result) -> str:
    if _is_payload(result):
        text = f"rendered {len(result['nodes'])} nodes, {len(result['links'])} edges"
        # The number of categories is what a granularity change is judged by.
        color = (result.get("legend") or {}).get("node_color") or {}
        if color.get("type") == "categorical" and isinstance(color.get("mapping"), dict):
            text += f"; {color.get('attribute')}: {len(color['mapping'])} categories"
        return text
    if isinstance(result, dict):
        for key in ("message", "content", "result"):
            if isinstance(result.get(key), str):
                return result[key][:300]
        return json.dumps(result, ensure_ascii=False, default=str)[:300]
    return str(result)[:300]


def _utc(moment) -> datetime:
    """Comparable UTC datetime; SQLite hands timezone-aware columns back naive."""
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _format_value(value) -> str:
    return "auto" if value is None else json.dumps(value, ensure_ascii=False)


# --- lifecycle --------------------------------------------------------------


def _earlier_calls(db, chat_id, tools) -> list[dict]:
    """Successful calls of `tools` from earlier turns of this chat, oldest first.

    A user often asks to tune a result in the turn after it was drawn ("make
    the granularity adjustable"), so the pipeline cannot be limited to this
    turn. Stored arguments are the model's; `network_id` is filled in by
    `_build` exactly as the normalizer would have.
    """
    rows = (
        db.query(models.ToolExecution)
        .join(models.ChatMessage, models.ToolExecution.message_id == models.ChatMessage.id)
        .filter(
            models.ChatMessage.chat_id == chat_id,
            models.ToolExecution.tool_name.in_(list(tools)),
            models.ToolExecution.status == "completed",
        )
        .order_by(models.ToolExecution.id)
        .all()
    )
    return [
        {"name": row.tool_name, "args": row.arguments or {}, "status": "completed"}
        for row in rows
    ]


def _build(form: TuningForm, turn_state: dict, network_id: int, earlier=()):
    # This turn's calls come last, so they win over earlier turns.
    executed = list(earlier) + list(turn_state.get("executed_calls") or [])
    catalog = turn_state.get("tool_catalog")

    steps = []
    for tool in form.tools:
        if not is_tunable_tool(tool):
            raise TuningError(
                f"'{tool}' cannot be re-run from a tuning panel: only analysis_*, "
                "layout_* and visualization_* tools that keep the current view can."
            )
        runs = [
            c
            for c in executed
            if c["name"] == tool
            and c["status"] == "completed"
            and (c.get("args") or {}).get("network_id", network_id) == network_id
        ]
        if not runs:
            raise TuningError(
                f"'{tool}' has not run successfully on the current view. Run the "
                f"pipeline first, then call {OFFER_TOOL} for it."
            )
        arguments = copy.deepcopy(runs[-1].get("args") or {})
        arguments["network_id"] = network_id
        steps.append({"tool": tool, "arguments": arguments})
    base = {step["tool"]: step["arguments"] for step in steps}

    specs, values, suggested = [], {}, {}
    for field in form.fields:
        properties = _properties(catalog, field.tool)
        prop = properties.get(field.argument)
        if prop is None:
            raise TuningError(
                f"'{field.tool}' has no argument '{field.argument}'. "
                f"Available: {', '.join(sorted(properties))}"
            )
        types = _schema_types(prop)
        integer = "integer" in types and "number" not in types
        spec = field.model_dump()
        spec.update(
            id=field.id,
            description=prop.get("description") or "",
            integer=integer,
        )
        if field.kind == "select":
            enum = _schema_value(prop, "enum")
            if enum and not set(field.options) <= set(enum):
                raise TuningError(f"{field.id}: options must be among {enum}")
        else:
            if not types & {"number", "integer"}:
                raise TuningError(
                    f"{field.id} is not numeric; use kind='select' with its options."
                )
            low, high = _schema_value(prop, "minimum"), _schema_value(prop, "maximum")
            if low is not None and field.minimum is not None and field.minimum < low:
                raise TuningError(f"{field.id}: minimum is below the tool's bound {low}")
            if high is not None and field.maximum is not None and field.maximum > high:
                raise TuningError(f"{field.id}: maximum is above the tool's bound {high}")
            if integer:
                spec["step"] = field.step if field.step is not None else 1
                bounds = (spec["step"], field.minimum, field.maximum)
                if any(v is not None and not float(v).is_integer() for v in bounds):
                    raise TuningError(
                        f"{field.id} is an integer: minimum, maximum and step must be whole"
                    )

        recommended = field.suggested
        if recommended is not None:
            recommended = coerce_value(spec, recommended, label=f"{field.id} suggested")

        current = base[field.tool].get(field.argument, _schema_value(prop, "default"))
        if current is None:
            if recommended is None:
                raise TuningError(
                    f"{field.id} ran with its automatic default, so the panel has no "
                    "current value. Pass `suggested` with the effective value the tool "
                    "reported, or your recommendation."
                )
            current = recommended
        elif field.kind == "select":
            current = coerce_value(spec, current, label=f"{field.id} current value")
        elif (field.minimum is not None and current < field.minimum) or (
            field.maximum is not None and current > field.maximum
        ):
            raise TuningError(
                f"{field.id} currently is {current}, outside "
                f"{_format_bounds(spec)}; widen the range to include it."
            )

        specs.append(spec)
        values[field.id] = current
        suggested[field.id] = recommended if recommended is not None else current

    return specs, steps, values, suggested


def present_tuning(chat_id, db, arguments, turn_state) -> dict:
    """`offer_parameter_tuning`: persist a panel for the pipeline that just ran."""
    try:
        form = TuningForm.model_validate(arguments)
    except ValidationError as error:
        return {"error": _readable(error)}
    chat = db.query(models.Chat).filter_by(id=chat_id).with_for_update().one()
    try:
        fields, steps, values, suggested = _build(
            form, turn_state, chat.network_id, _earlier_calls(db, chat_id, form.tools)
        )
    except TuningError as error:
        return {"error": str(error)}

    db.query(models.ParameterTuning).filter_by(chat_id=chat_id, status="active").update(
        {"status": "superseded"}
    )
    row = models.ParameterTuning(
        id=str(uuid4()),
        chat_id=chat_id,
        network_id=chat.network_id,
        specification={"question": form.question, "fields": fields},
        steps=steps,
        values=values,
        initial_values=dict(values),
        suggested_values=suggested,
        history=[],
        status="active",
        activated_tools=sorted(turn_state.get("enabled_tool_names") or ()),
    )
    db.add(row)
    db.commit()

    # The words the user answers with in this same turn are handled here too.
    catalog = turn_state.get("tool_catalog")
    if catalog is not None:
        catalog.activate([APPLY_TOOL], turn_state)
    return {"parameter_tuning": serialize_tuning(row, chat.network_id)}


def serialize_tuning(row, active_network_id) -> dict:
    status = row.status
    if status == "active" and row.network_id != active_network_id:
        status = "expired"
    return {
        "id": row.id,
        "chat_id": row.chat_id,
        "network_id": row.network_id,
        "status": status,
        "question": row.specification["question"],
        "fields": row.specification["fields"],
        "steps": row.steps,
        "values": row.values,
        "initial_values": row.initial_values,
        "suggested_values": row.suggested_values,
        "history": row.history or [],
        "last_result": row.last_result,
        "last_applied_at": row.last_applied_at.isoformat()
        if row.last_applied_at
        else None,
    }


def active_tuning(db, chat_id, network_id):
    return (
        db.query(models.ParameterTuning)
        .filter_by(chat_id=chat_id, network_id=network_id, status="active")
        .order_by(models.ParameterTuning.created_at.desc())
        .first()
    )


async def apply(
    db,
    row,
    changes: dict[str, Any],
    *,
    source: Literal["agent", "form"],
    active_network_id: int,
    schemas: dict[str, dict] | None = None,
    session=None,
    queue=None,
) -> dict:
    """Re-run the pipeline with `changes` ({"tool.argument": value}) and draw it.

    Only the agent may change arguments that are not panel fields. Nothing is
    persisted unless every step succeeds.
    """
    if row.status != "active" or row.network_id != active_network_id:
        raise TuningInactive("This tuning panel is no longer active")
    if not changes:
        raise TuningError("No changes given")

    fields = {spec["id"]: spec for spec in row.specification["fields"]}
    steps = copy.deepcopy(row.steps)
    by_tool = {step["tool"]: step for step in steps}
    values = dict(row.values)
    diff = []
    for param, value in changes.items():
        tool, _, argument = param.partition(".")
        if param in fields:
            value = coerce_value(fields[param], value)
            before = values.get(param)
            values[param] = value
        else:
            if source != "agent":
                raise TuningError(f"'{param}' is not a field of this panel")
            if tool not in by_tool:
                raise TuningError(
                    f"'{tool}' is not part of this pipeline ({', '.join(by_tool)})"
                )
            if argument == "network_id":
                raise TuningError("network_id cannot be tuned")
            if schemas is not None and argument not in schemas.get(tool, {}):
                raise TuningError(f"'{tool}' has no argument '{argument}'")
            before = by_tool[tool]["arguments"].get(argument)
        if value is None:
            by_tool[tool]["arguments"].pop(argument, None)
        else:
            by_tool[tool]["arguments"][argument] = value
        if before != value:
            diff.append({"param": param, "before": before, "after": value})

    if not diff:
        return {"changes": [], "values": values, "steps": [], "visualization": None}

    results, last = [], None
    for step in steps:
        try:
            result = await mcp_client.execute_tool(
                step["tool"], step["arguments"], session=session
            )
        except Exception as exc:
            raise TuningExecutionError(step["tool"], str(exc)) from exc
        if isinstance(result, dict) and result.get("error"):
            raise TuningExecutionError(step["tool"], str(result["error"]))
        results.append({"tool": step["tool"], "message": _summarize(result)})
        last = result

    visualization = last if _is_payload(last) else None
    if visualization is None:
        try:
            generated = await mcp_client.execute_tool(
                "visualization_generate", {"network_id": row.network_id}, session=session
            )
        except Exception as exc:
            raise TuningExecutionError("visualization_generate", str(exc)) from exc
        visualization = generated if _is_payload(generated) else None

    now = datetime.now(timezone.utc)
    if visualization is not None:
        if queue is not None:
            await emitters.emit_render_update(queue, visualization)
        chat = db.get(models.Chat, row.chat_id)
        if chat is not None:
            chat.visualization_state = visualization

    history = list(row.history or [])
    history.append(
        {
            "changes": diff,
            "source": source,
            "summary": results[-1]["message"] if results else "",
            "at": now.isoformat(),
        }
    )
    row.history = history[-MAX_HISTORY:]
    row.steps = steps
    row.values = values
    row.last_result = results
    row.last_applied_at = now
    if source == "agent":
        # The agent made (and reports) this change itself.
        row.reported_at = now
    db.commit()
    return {
        "changes": diff,
        "values": values,
        "steps": results,
        "visualization": visualization,
    }


async def apply_from_agent(chat_id, db, arguments, turn_state, queue=None, session=None):
    """`apply_parameter_tuning`: the words path onto the shared state."""
    try:
        request = ApplyRequest.model_validate(arguments)
    except ValidationError as error:
        return {"error": _readable(error)}
    chat = db.query(models.Chat).filter_by(id=chat_id).one()
    query = db.query(models.ParameterTuning).filter_by(chat_id=chat_id, status="active")
    if request.tuning_id:
        row = query.filter_by(id=request.tuning_id).first()
    else:
        row = active_tuning(db, chat_id, chat.network_id)
    if row is None:
        return {
            "error": "No active tuning panel for this view. Re-run the tool directly "
            f"with the new value instead (and {OFFER_TOOL} afterwards if useful)."
        }

    catalog = turn_state.get("tool_catalog")
    schemas = None
    if catalog is not None:
        schemas = {}
        for step in row.steps:
            definition = catalog.get(step["tool"])
            schemas[step["tool"]] = (
                ((definition.parameters or {}).get("properties") or {})
                if definition
                else {}
            )

    try:
        outcome = await apply(
            db,
            row,
            {change.param: change.value for change in request.changes},
            source="agent",
            active_network_id=chat.network_id,
            schemas=schemas,
            session=session,
            queue=queue,
        )
    except (TuningError, TuningExecutionError) as error:
        db.rollback()
        return {"error": str(error)}
    return {
        "tuning_id": row.id,
        "changes": outcome["changes"],
        "values": outcome["values"],
        "steps": outcome["steps"],
    }


def confirm(chat, db, tuning_id, content: str):
    """Called under the chat row lock. Returns the user message text, or None on retry."""
    row = (
        db.query(models.ParameterTuning)
        .filter_by(id=tuning_id, chat_id=chat.id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise LookupError("Tuning panel not found in this chat")
    if row.status == "confirmed":
        return None
    if row.status != "active" or row.network_id != chat.network_id:
        raise ValueError("This tuning panel is no longer active")
    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    lines = [(content or "").strip() or row.specification["question"]]
    lines += [f"{param} = {_format_value(value)}" for param, value in row.values.items()]
    return "\n".join(lines)


def latest_confirmed(db, chat_id, network_id):
    return (
        db.query(models.ParameterTuning)
        .filter_by(chat_id=chat_id, network_id=network_id, status="confirmed")
        .order_by(models.ParameterTuning.confirmed_at.desc())
        .first()
    )


def offerable_pipeline(db, chat_id, network_id, user_text: str) -> list[str] | None:
    """The pipeline behind the current view, when the user asks to tune it.

    Only for requests that match the `parameter-tuning` skill: otherwise the
    offer tool stays behind progressive disclosure (ADR 0010). The pipeline is
    the last analysis/layout call on this view plus the visualization calls
    that followed it.
    """
    from .skills import registry as skill_registry

    if not any(s.name == "parameter-tuning" for s in skill_registry.suggest(user_text)):
        return None
    rows = (
        db.query(models.ToolExecution.tool_name, models.ToolExecution.arguments)
        .join(models.ChatMessage, models.ToolExecution.message_id == models.ChatMessage.id)
        .filter(
            models.ChatMessage.chat_id == chat_id,
            models.ToolExecution.status == "completed",
        )
        .order_by(models.ToolExecution.id)
        .all()
    )
    names = [
        name
        for name, arguments in rows
        if is_tunable_tool(name)
        and (arguments or {}).get("network_id", network_id) == network_id
    ]
    starts = [i for i, name in enumerate(names) if not name.startswith("visualization_")]
    if not starts:
        return None
    after = [n for n in dict.fromkeys(names[starts[-1] + 1 :]) if n.startswith("visualization_")]
    return [names[starts[-1]], *after]


def offer_hint(pipeline: list[str]) -> str:
    return (
        "# Tunable View\n"
        f"The current view was drawn by {' → '.join(pipeline)}. The user is asking "
        "about its parameters: change them from their words by re-running these "
        f"tools, and to make them adjustable call {OFFER_TOOL} with "
        f"tools={pipeline} (it reuses the arguments those calls ran with). Do not "
        "use ask_user for parameter values."
    )


def context_block(db, row) -> str:
    """What the agent must know about an active panel at the start of a turn.

    Marks panel changes as reported, so each is announced once.
    """
    steps = " → ".join(step["tool"] for step in row.steps)
    lines = [
        "# Active Parameter Tuning",
        f"A tuning panel (id {row.id}) is attached to the current view. Pipeline, "
        f"re-run on every change: {steps}.",
        "Fields (current value; suggested value; explored range; low → high meaning):",
    ]
    for spec in row.specification["fields"]:
        current = row.values.get(spec["id"])
        suggested = row.suggested_values.get(spec["id"])
        detail = f"- {spec['id']} = {_format_value(current)}"
        if suggested != current:
            detail += f"; suggested {_format_value(suggested)} (not applied)"
        if spec["kind"] == "select":
            detail += f"; options {spec['options']}"
        else:
            detail += f"; range {_format_bounds(spec)}"
        if spec.get("low_label") or spec.get("high_label"):
            detail += f"; {spec.get('low_label') or '?'} → {spec.get('high_label') or '?'}"
        lines.append(detail)

    history = row.history or []
    if history:
        lines.append("Recent changes, oldest first:")
        for entry in history[-5:]:
            changed = ", ".join(
                f"{c['param']} {_format_value(c['before'])} → {_format_value(c['after'])}"
                for c in entry["changes"]
            )
            lines.append(f"- {entry['source']}: {changed}")

    unreported = [
        entry
        for entry in history
        if entry["source"] == "form"
        and (row.reported_at is None or _utc(entry["at"]) > _utc(row.reported_at))
    ]
    if unreported:
        changed = "; ".join(
            f"{c['param']} {_format_value(c['before'])} → {_format_value(c['after'])}"
            for entry in unreported
            for c in entry["changes"]
        )
        lines.append(
            "Since your last reply the user applied from the panel: "
            f"{changed}. The canvas already shows these values."
        )
    lines.append(
        f"To change any argument of these pipeline tools, including ones that are "
        f"not fields, call {APPLY_TOOL} with every change in one call, converting "
        "relative requests from the current value, range and history. Do not call "
        "the pipeline tools directly for such adjustments. Report parameter names "
        "with the before → after values it returns."
    )

    row.reported_at = datetime.now(timezone.utc)
    db.commit()
    return "\n".join(lines)
