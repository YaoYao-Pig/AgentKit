from __future__ import annotations

from dataclasses import dataclass

from agentkit.config.models import SkillsIndexConfig

from .adapters.base import ToolAdapter, default_adapter_registry
from .interfaces import Executor
from .models import Action, ActionResult, EvidenceRef, PipelineState, Summary


@dataclass(slots=True)
class SkillDispatcherExecutor(Executor):
    skills_index: SkillsIndexConfig
    adapters: dict[str, ToolAdapter]

    @classmethod
    def from_skills_index(
        cls,
        skills_index: SkillsIndexConfig,
        workspace_root: str | None = None,
        allowed_paths: list[str] | None = None,
    ) -> "SkillDispatcherExecutor":
        return cls(
            skills_index=skills_index,
            adapters=default_adapter_registry(workspace_root=workspace_root, allowed_paths=allowed_paths),
        )

    def execute(self, action: Action, state: PipelineState) -> ActionResult:
        skill = self.skills_index.skills.get(action.action_type)
        if skill is None:
            return ActionResult(
                action_id=action.id,
                status="failed",
                summary=Summary(step_id=action.id, content=f"Unknown action_type '{action.action_type}'."),
                evidence=[EvidenceRef(path="dispatcher://skills", note="unregistered skill")],
                output={"error": "unknown_action_type", "action_type": action.action_type},
            )

        adapter = self.adapters.get(skill.adapter)
        if adapter is None:
            return ActionResult(
                action_id=action.id,
                status="failed",
                summary=Summary(
                    step_id=action.id,
                    content=f"No adapter registered for '{skill.adapter}'.",
                ),
                evidence=[EvidenceRef(path="dispatcher://adapters", note="missing adapter")],
                output={"error": "unknown_adapter", "adapter": skill.adapter},
            )

        try:
            return adapter.execute(action, state, skill)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(
                action_id=action.id,
                status="failed",
                summary=Summary(step_id=action.id, content=f"Adapter execution failed: {exc}"),
                evidence=[EvidenceRef(path=f"adapter://{skill.adapter}", note="exception")],
                output={"error": "adapter_exception", "message": str(exc)},
            )
