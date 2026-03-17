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
    forbid_manual_business_edits: bool = False
    require_api_patch_for_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModuleRulesConfig:
    allowed_paths: list[str] = field(default_factory=list)
    disallowed_dependencies: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeConfig:
    max_steps: int = 5
    default_action_type: str = "mock_action"
    api_host: str = "127.0.0.1"
    api_port: int = 8787
    require_api_token: bool = False
    api_token: str = ""
    api_log_level: str = "INFO"
    api_log_to_file: bool = True
    api_log_file: str = ".agentkit/logs/agentkit-serve.log"
    strict_codegen_mode: bool = False
    strict_industrial_mode: bool = False
    strict_industrial_auto_init_git: bool = False
    strict_production_mode: bool = False
    llm_healthcheck_required: bool = False
    llm_endpoint_timeout_sec: int = 3
    llm_api_key_env: str = "AGENTKIT_LLM_API_KEY"


@dataclass(slots=True)
class FullConfig:
    system_profile: SystemProfileConfig
    skills_index: SkillsIndexConfig
    policy_rules: PolicyRulesConfig
    module_rules: ModuleRulesConfig
    runtime: RuntimeConfig
