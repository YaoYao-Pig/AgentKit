from __future__ import annotations

import logging
import os
import socket
from urllib.parse import urlparse

from agentkit.config.models import FullConfig

from .task_spec import TaskRunSpec


logger = logging.getLogger("agentkit.guard")


def _is_endpoint_reachable(endpoint: str, timeout_sec: int) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def enforce_strict_codegen(config: FullConfig, spec: TaskRunSpec) -> None:
    runtime = config.runtime
    if not runtime.strict_codegen_mode:
        return

    chosen_action = spec.action_type or runtime.default_action_type
    if chosen_action != "llm_codegen":
        raise ValueError(
            "strict_codegen_mode is enabled: task action_type must be 'llm_codegen' "
            f"(resolved action_type='{chosen_action}')"
        )

    llm_skill = config.skills_index.skills.get("llm_codegen")
    if llm_skill is None:
        raise ValueError("strict_codegen_mode is enabled but skill 'llm_codegen' is not configured")

    patch_skill = config.skills_index.skills.get("apply_generated_patch")
    if patch_skill is None:
        raise ValueError("strict_codegen_mode is enabled but skill 'apply_generated_patch' is not configured")

    endpoint = str((llm_skill.static_params or {}).get("endpoint") or "").strip()
    if not endpoint:
        raise ValueError("strict_codegen_mode requires llm_codegen.static_params.endpoint")

    key_env_name = runtime.llm_api_key_env.strip() or "AGENTKIT_LLM_API_KEY"
    api_key = os.getenv(key_env_name, "").strip()
    if not api_key:
        raise ValueError(
            f"strict_codegen_mode requires environment variable '{key_env_name}' to be set"
        )

    if runtime.llm_healthcheck_required:
        timeout_sec = max(1, int(runtime.llm_endpoint_timeout_sec))
        if not _is_endpoint_reachable(endpoint, timeout_sec):
            raise ValueError(
                "strict_codegen_mode healthcheck failed: endpoint is unreachable "
                f"endpoint='{endpoint}' timeout={timeout_sec}s"
            )

    prompt = str(spec.action_params.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("strict_codegen_mode requires task action_params.prompt")

    if runtime.strict_industrial_mode:
        if not config.policy_rules.forbid_manual_business_edits:
            raise ValueError(
                "strict_industrial_mode requires policy_rules.forbid_manual_business_edits=true"
            )
        if not config.policy_rules.require_api_patch_for_paths:
            raise ValueError(
                "strict_industrial_mode requires non-empty policy_rules.require_api_patch_for_paths"
            )

    logger.info(
        "strict_codegen_mode checks passed action=%s endpoint=%s key_env=%s healthcheck=%s strict_industrial=%s",
        chosen_action,
        endpoint,
        key_env_name,
        runtime.llm_healthcheck_required,
        runtime.strict_industrial_mode,
    )
