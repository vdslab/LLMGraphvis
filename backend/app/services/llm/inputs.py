"""Validated, persistent questions; the model declares controls, never HTML."""

import json
import math
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common import models


class InputField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(
        pattern=r"^[a-z][a-z0-9_]{0,39}$",
        description="Stable field key, lowercase letters/numbers/underscores.",
    )
    label: str = Field(
        min_length=1,
        max_length=160,
        description="Short user-facing label in the conversation language.",
    )
    kind: Literal["select", "multiselect", "slider", "number", "text"] = Field(
        description="select for one goal; multiselect for combinable choices; "
        "slider/number for numeric settings; text for an open question."
    )
    options: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="2–12 actual candidates for selection controls. Usually 3 "
        "for analysis goals. Do not include Other: the UI adds it separately.",
    )
    allow_other: bool = Field(
        default=True,
        description=(
            "Selection controls include Other/free-text by default. "
            "Do not add Other to options. Ignored for non-selection controls."
        ),
    )
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    step: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def normalize_title_alias(cls, value):
        """Accept a common model-generated `title` alias as `label`.

        The advertised schema remains `label`; this normalization only prevents
        a recoverable chat error when a model adds or substitutes `title`.
        Unknown keys still fail under ``extra='forbid'``.
        """
        if not isinstance(value, dict) or "title" not in value:
            return value
        normalized = dict(value)
        title = normalized.pop("title")
        if not normalized.get("label"):
            normalized["label"] = title
        return normalized

    @model_validator(mode="after")
    def check_controls(self):
        if any(not option.strip() or len(option) > 160 for option in self.options):
            raise ValueError("Options must be nonempty and at most 160 characters")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Options must be unique")
        if self.kind in {"select", "multiselect"}:
            if len(self.options) < 2:
                raise ValueError("Selection controls need at least two options")
        elif self.options:
            raise ValueError("Only selection controls accept options")
        if self.kind == "slider" and (self.minimum is None or self.maximum is None):
            raise ValueError("Sliders require minimum and maximum")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum >= self.maximum:
                raise ValueError("minimum must be less than maximum")
        if self.kind not in {"slider", "number"}:
            if any(
                value is not None for value in (self.minimum, self.maximum, self.step)
            ):
                raise ValueError("Only numeric controls accept bounds/step")
        return self

    def _valid_other(self, value):
        return (
            self.allow_other
            and isinstance(value, dict)
            and set(value) == {"other"}
            and isinstance(value["other"], str)
            and bool(value["other"].strip())
            and len(value["other"]) <= 4000
        )

    def validate_answer(self, value):
        if self.kind == "select":
            valid = (
                isinstance(value, str) and value in self.options
            ) or self._valid_other(value)
        elif self.kind == "multiselect":
            valid = (
                isinstance(value, list)
                and bool(value)
                and all(
                    (isinstance(item, str) and item in self.options)
                    or self._valid_other(item)
                    for item in value
                )
            )
            valid = valid and (
                len([item for item in value if isinstance(item, str)])
                == len({item for item in value if isinstance(item, str)})
                and sum(isinstance(item, dict) for item in value) <= 1
            )
        elif self.kind == "text":
            valid = (
                isinstance(value, str) and bool(value.strip()) and len(value) <= 4000
            )
        else:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
            valid = valid and math.isfinite(value)
            if valid and self.minimum is not None:
                valid = value >= self.minimum
            if valid and self.maximum is not None:
                valid = value <= self.maximum
            if valid and self.step is not None:
                steps = (value - (self.minimum or 0)) / self.step
                valid = math.isclose(steps, round(steps), abs_tol=1e-8)
        if not valid:
            raise ValueError(f"Invalid answer for '{self.label}'")
        return value


def format_answer(value):
    if isinstance(value, dict):
        return f"Other: {value['other']}"
    if isinstance(value, list):
        return ", ".join(format_answer(item) for item in value)
    return str(value)


class InputForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    fields: list[InputField] = Field(min_length=1, max_length=6)

    @model_validator(mode="before")
    @classmethod
    def normalize_fields_input(cls, value):
        """Recover from malformed model outputs for the fields parameter.

        Models (notably Claude/Anthropic) occasionally emit tool calls where:
        1. `fields` is a JSON-encoded string, sometimes prefixed or wrapped by
           internal XML tags such as `\\n<parameter name="fields">[{"id": ...}]`.
        2. `fields` is a single dict rather than a list of dicts.
        3. Field parameters (`id`, `label`, `kind`, `options`) are flattened
           into the top-level arguments dictionary rather than nested under `fields`.
        4. Field strings (e.g., `id`, `label`) contain leaked XML tags.
        """
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        raw_fields = normalized.get("fields")

        # Case 1: `fields` is a string
        if isinstance(raw_fields, str):
            cleaned = raw_fields.strip()
            parsed = None
            match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", cleaned)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                except Exception:
                    parsed = None
            if parsed is None:
                stripped = re.sub(r"<[^>]+>", "", cleaned).strip()
                if stripped.startswith("[") or stripped.startswith("{"):
                    try:
                        parsed = json.loads(stripped)
                    except Exception:
                        parsed = None

            if isinstance(parsed, list):
                raw_fields = parsed
                normalized["fields"] = raw_fields
            elif isinstance(parsed, dict):
                raw_fields = [parsed]
                normalized["fields"] = raw_fields

        # Case 2: `fields` is a dict
        if isinstance(raw_fields, dict):
            raw_fields = [raw_fields]
            normalized["fields"] = raw_fields

        # Case 3: Field keys are flattened at the top level
        field_keys = {
            "id",
            "label",
            "kind",
            "options",
            "allow_other",
            "minimum",
            "maximum",
            "step",
            "title",
        }
        has_flattened_attrs = any(k in normalized for k in ("kind", "options", "label"))
        if not isinstance(normalized.get("fields"), list) and has_flattened_attrs:
            extracted_field = {}
            for k in list(normalized.keys()):
                if k in field_keys:
                    extracted_field[k] = normalized.pop(k)
            if "id" not in extracted_field:
                if isinstance(raw_fields, str):
                    candidate_id = re.sub(r"<[^>]+>", "", raw_fields).strip()
                    if candidate_id and re.fullmatch(r"^[a-z][a-z0-9_]{0,39}$", candidate_id):
                        extracted_field["id"] = candidate_id
                if "id" not in extracted_field:
                    extracted_field["id"] = "goal"
            normalized["fields"] = [extracted_field]

        # Case 4: Clean up any residual XML tags inside field dictionaries
        if isinstance(normalized.get("fields"), list):
            cleaned_list = []
            for item in normalized["fields"]:
                if isinstance(item, dict):
                    clean_item = dict(item)
                    for k, v in clean_item.items():
                        if isinstance(v, str) and ("<" in v and ">" in v):
                            clean_item[k] = re.sub(r"<[^>]+>", "", v).strip()
                    cleaned_list.append(clean_item)
                else:
                    cleaned_list.append(item)
            normalized["fields"] = cleaned_list

        return normalized

    @model_validator(mode="before")
    @classmethod
    def normalize_split_selection_fields(cls, value):
        """Recover when a model creates multiple select fields each holding one option.

        When presenting a set of alternative analysis goals, models occasionally
        declare N separate `select` fields, each with a single candidate in its
        `options` list, instead of declaring one `select` field containing N options.
        Because select controls require at least two options, every field in that
        structure fails validation.
        When all fields in the request are select controls with exactly one option,
        merge them into a single select control with all distinct options.
        """
        if not isinstance(value, dict) or "fields" not in value:
            return value
        raw_fields = value.get("fields")
        if not isinstance(raw_fields, list) or len(raw_fields) < 2:
            return value

        is_split_select = all(
            isinstance(f, dict)
            and f.get("kind") == "select"
            and isinstance(f.get("options"), list)
            and len(f.get("options")) == 1
            and isinstance(f.get("options")[0], str)
            for f in raw_fields
        )
        if not is_split_select:
            return value

        merged_options = []
        for f in raw_fields:
            opt = f["options"][0].strip()
            if opt and opt not in merged_options:
                merged_options.append(opt)

        if len(merged_options) >= 2:
            question = str(value.get("question", ""))
            has_japanese = any(
                "\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff"
                for c in question
            )
            default_label = "分析目的" if has_japanese else "Analysis goal"

            primary_id = str(raw_fields[0].get("id", "goal"))
            clean_id = (
                primary_id.rsplit("_", 1)[0]
                if "_" in primary_id and primary_id.rsplit("_", 1)[1].isdigit()
                else primary_id
            )
            if not clean_id or not clean_id[0].isalpha():
                clean_id = "goal"

            allow_other = any(f.get("allow_other", True) is not False for f in raw_fields)

            normalized = dict(value)
            normalized["fields"] = [
                {
                    "id": clean_id,
                    "kind": "select",
                    "label": default_label,
                    "options": merged_options,
                    "allow_other": allow_other,
                }
            ]
            return normalized

        return value

    @model_validator(mode="after")
    def unique_fields(self):
        if len({field.id for field in self.fields}) != len(self.fields):
            raise ValueError("Field IDs must be unique")
        return self

    def answer_text(self, values: dict) -> str:
        if set(values) != {field.id for field in self.fields}:
            raise ValueError("Answer every field, using only the requested field IDs")
        lines = [self.question]
        for field in self.fields:
            value = field.validate_answer(values[field.id])
            text = format_answer(value)
            lines.append(f"{field.label}: {text}")
        return "\n".join(lines)


def present_question(chat_id, db, arguments, turn_state):
    form = InputForm.model_validate(arguments)
    chat = db.query(models.Chat).filter_by(id=chat_id).with_for_update().one()
    db.query(models.AnalysisInput).filter_by(chat_id=chat_id, status="pending").update(
        {"status": "superseded"}
    )
    request = models.AnalysisInput(
        id=str(uuid4()),
        chat_id=chat_id,
        network_id=chat.network_id,
        specification=form.model_dump(),
        status="pending",
    )
    db.add(request)
    db.commit()
    result = serialize_request(request, chat.network_id)
    turn_state["input_request"] = result
    return {"input_request": result}


def serialize_request(request, active_network_id):
    status = request.status
    if status == "pending" and request.network_id != active_network_id:
        status = "expired"
    return {
        "id": request.id,
        "chat_id": request.chat_id,
        "network_id": request.network_id,
        "status": status,
        **request.specification,
        "answer": request.answer,
    }


def accept_answer(chat, db, request_id, values, content):
    """Called under the chat row lock; caller commits with the user message."""
    request = (
        db.query(models.AnalysisInput)
        .filter_by(id=request_id, chat_id=chat.id)
        .with_for_update()
        .first()
    )
    if request is None:
        raise LookupError("Question not found in this chat")
    answer = values if values is not None else {"free_text": content.strip()}
    if request.status == "answered" and request.answer == answer:
        return None  # Idempotent retry: no second message or LLM execution.
    if request.status != "pending" or request.network_id != chat.network_id:
        raise ValueError("This question is no longer active")
    form = InputForm.model_validate(request.specification)
    text = form.answer_text(values) if values is not None else content.strip()
    if not text:
        raise ValueError("An answer is required")
    request.status = "answered"
    request.answer = values if values is not None else {"free_text": text}
    return text
