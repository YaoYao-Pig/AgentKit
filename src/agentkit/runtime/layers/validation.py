from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..interfaces import Validator
from ..models import Action, ActionResult, PipelineState, PolicyDecision, PolicyResult


@dataclass(slots=True)
class SimpleValidator(Validator):
    blocked_action_types: set[str]
    review_action_types: set[str] = field(default_factory=set)
    allowed_paths: list[str] = field(default_factory=list)

    def _normalized_allowed_paths(self) -> list[str]:
        out: list[str] = []
        for item in self.allowed_paths:
            prefix = str(item).replace("\\", "/").lstrip("./")
            if not prefix:
                continue
            if not prefix.endswith("/"):
                prefix += "/"
            out.append(prefix)
        return sorted(set(out))

    def _extract_action_paths(self, action: Action) -> list[str]:
        paths: list[str] = []

        direct = action.params.get("path") or action.params.get("target_path")
        if isinstance(direct, str) and direct.strip():
            paths.append(direct.strip())

        raw_paths = action.params.get("paths")
        if isinstance(raw_paths, list):
            paths.extend(str(item).strip() for item in raw_paths if str(item).strip())

        patches = action.params.get("patches")
        if isinstance(patches, list):
            for item in patches:
                if isinstance(item, dict) and item.get("path"):
                    paths.append(str(item["path"]).strip())

        return paths

    def _check_allowed_paths(self, action: Action) -> PolicyResult | None:
        allowed = self._normalized_allowed_paths()
        if not allowed:
            return None

        for raw in self._extract_action_paths(action):
            rel = Path(raw)
            if rel.is_absolute() or ".." in rel.parts:
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"unsafe path in action params: {raw}",
                    risk_level="high",
                )
            normalized = rel.as_posix().lstrip("./")
            if not any(normalized.startswith(prefix) for prefix in allowed):
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"path '{normalized}' is outside module_rules.allowed_paths",
                    risk_level="high",
                )
        return None

    def pre_check(self, action: Action, state: PipelineState) -> PolicyResult:
        if action.action_type in self.blocked_action_types:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"action type '{action.action_type}' is blocked",
                risk_level="high",
            )

        path_check = self._check_allowed_paths(action)
        if path_check is not None:
            return path_check

        if action.action_type in self.review_action_types:
            return PolicyResult(
                decision=PolicyDecision.REQUIRE_REVIEW,
                reason=f"action type '{action.action_type}' requires review",
                risk_level="medium",
            )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="pre-check passed")

    def post_check(self, result: ActionResult, state: PipelineState) -> PolicyResult:
        if result.status != "success":
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason="post-check detected failed execution",
                risk_level="medium",
            )
        return PolicyResult(decision=PolicyDecision.ALLOW, reason="post-check passed")
