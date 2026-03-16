from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(slots=True)
class TaskRunSpec:
    id: str
    title: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    input_sources: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    validation_checklist: list[str] = field(default_factory=list)
    rollback_plan: list[str] = field(default_factory=list)
    risk_points: list[str] = field(default_factory=list)
    action_type: str | None = None
    action_params: dict[str, object] = field(default_factory=dict)
    module_hints: list[str] = field(default_factory=list)


def load_task_run_spec(path: str) -> TaskRunSpec:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("task spec must be a YAML mapping")

    action = raw.get("action", {})
    if action is None:
        action = {}
    if not isinstance(action, dict):
        raise ValueError("task spec 'action' must be a mapping")

    context = raw.get("context", {})
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("task spec 'context' must be a mapping")

    return TaskRunSpec(
        id=str(raw["id"]),
        title=str(raw.get("title", raw["id"])),
        goal=str(raw["goal"]),
        constraints=[str(x) for x in raw.get("constraints", [])],
        success_criteria=[str(x) for x in raw.get("success_criteria", [])],
        input_sources=[str(x) for x in raw.get("input_sources", [])],
        affected_files=[str(x) for x in raw.get("affected_files", [])],
        validation_checklist=[str(x) for x in raw.get("validation_checklist", [])],
        rollback_plan=[str(x) for x in raw.get("rollback_plan", [])],
        risk_points=[str(x) for x in raw.get("risk_points", [])],
        action_type=str(action["type"]) if "type" in action else None,
        action_params={str(k): v for k, v in dict(action.get("params", {})).items()},
        module_hints=[str(x) for x in context.get("module_hints", [])],
    )
