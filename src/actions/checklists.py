"""Validated evidence/action checklists that contain no legal conclusions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, model_validator

from src.models.schemas import NonEmptyText, StrictModel


class ChecklistError(RuntimeError):
    """A bounded checklist loading or lookup failure."""


class ChecklistItem(StrictModel):
    item_id: Annotated[str, Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)]
    label: NonEmptyText
    sensitive: StrictBool


class ChecklistTemplate(StrictModel):
    template_id: Annotated[str, Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)]
    title: NonEmptyText
    scenario: Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
    domain: Literal["labour", "criminal", "tenancy_property"]
    guidance_label: NonEmptyText
    items: Annotated[tuple[ChecklistItem, ...], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def unique_items(self) -> ChecklistTemplate:
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("checklist item_id values must be unique within a template")
        if "guidance" not in self.guidance_label.casefold():
            raise ValueError("guidance_label must explicitly label the checklist as guidance")
        return self


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ChecklistError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class ChecklistCatalog:
    """Immutable exact-ID lookup over versioned local checklist templates."""

    def __init__(self, path: str | Path) -> None:
        source = Path(path)
        try:
            if source.stat().st_size > 512 * 1024:
                raise ChecklistError("checklist catalogue exceeds the local size limit")
            payload = json.loads(
                source.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
            )
        except ChecklistError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ChecklistError("could not load a valid checklist catalogue") from exc
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "templates"}:
            raise ChecklistError("checklist catalogue has an invalid root shape")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ChecklistError("unsupported checklist schema_version")
        if not isinstance(payload["templates"], list):
            raise ChecklistError("templates must be a JSON array")
        try:
            templates = tuple(ChecklistTemplate.model_validate(item) for item in payload["templates"])
        except (TypeError, ValueError) as exc:
            raise ChecklistError("a checklist template failed schema validation") from exc
        ids = [template.template_id for template in templates]
        if len(ids) != len(set(ids)):
            raise ChecklistError("duplicate checklist template_id detected")
        self.templates = templates
        self._by_id = {template.template_id: template for template in templates}

    def get(self, template_id: str) -> ChecklistTemplate:
        normalized = template_id.strip().casefold().replace("-", "_")
        if not normalized:
            raise ChecklistError("template_id must not be blank")
        try:
            return self._by_id[normalized]
        except KeyError as exc:
            raise ChecklistError(f"unknown checklist template_id: {normalized}") from exc
