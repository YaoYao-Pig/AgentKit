from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SystemProfileConfig:
    agent_name: str
    role: str
    boundaries: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkillConfig:
    purpose: str
    risk_level: str = "low"
    adapter: str = "mock"
    command: str | None = None
    module: str | None = None
    function: str | None = None
    static_params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillsIndexConfig:
    skills: dict[str, SkillConfig]


@dataclass(slots=True)
class PolicyRulesConfig:
    blocked_action_types: list[str] = field(default_factory=list)
    review_action_types: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModuleRulesConfig:
    allowed_paths: list[str] = field(default_factory=list)
    disallowed_dependencies: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeConfig:
    max_steps: int = 5
    default_action_type: str = "mock_action"


@dataclass(slots=True)
class FullConfig:
    system_profile: SystemProfileConfig
    skills_index: SkillsIndexConfig
    policy_rules: PolicyRulesConfig
    module_rules: ModuleRulesConfig
    runtime: RuntimeConfig
