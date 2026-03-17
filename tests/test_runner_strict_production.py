from pathlib import Path

import pytest

from agentkit.config.loader import load_full_config
from agentkit.config.models import RuntimeConfig
from agentkit.runner.api import _extract_codegen_payload, run_task
from agentkit.runtime.models import Action, ActionResult, ExecutionRecord, PipelineState, PolicyDecision, PolicyResult, RuntimeOutcome, Summary, TaskStatus
from agentkit.starter.init import initialize_starter_project


def _write_runtime_config(path: Path, *, strict_production: bool) -> None:
    path.write_text(
        "\n".join(
            [
                "max_steps: 6",
                "default_action_type: llm_codegen",
                "api_host: 127.0.0.1",
                "api_port: 8787",
                "require_api_token: false",
                "api_token: dev-agentkit-token",
                "api_log_level: INFO",
                "api_log_to_file: true",
                "api_log_file: .agentkit/logs/agentkit-serve.log",
                "strict_codegen_mode: true",
                "strict_industrial_mode: true",
                f"strict_production_mode: {'true' if strict_production else 'false'}",
                "llm_healthcheck_required: false",
                "llm_endpoint_timeout_sec: 2",
                "llm_api_key_env: AGENTKIT_LLM_API_KEY",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_policy_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "blocked_action_types: []",
                "review_action_types: []",
                "forbid_manual_business_edits: true",
                "require_api_patch_for_paths:",
                "  - src/",
                "  - tests/",
            ]
        )
        + "\n",
        encoding="utf-8",
    )



def _write_task_with_prompt(path: Path) -> None:
    path.write_text(
        """id: strict-prod-task-001
title: strict production endpoint check
goal: ensure endpoint constraints
constraints: []
success_criteria:
  - endpoint validated
input_sources: []
affected_files:
  - src/generated/strict_prod.txt
validation_checklist: []
rollback_plan: []
risk_points: []
action:
  type: llm_codegen
  params:
    prompt: hello
context:
  module_hints:
    - src/
""",
        encoding="utf-8",
    )
def test_strict_production_blocks_local_codegen_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "project"
    initialize_starter_project(target_dir=workspace, project_name="StrictProd", profile_name="minimal", force=True)
    _write_runtime_config(workspace / "configs" / "runtime.yaml", strict_production=True)
    _write_policy_config(workspace / "configs" / "policy_rules.yaml")
    monkeypatch.setenv("AGENTKIT_LLM_API_KEY", "dummy-key")
    _write_task_with_prompt(workspace / "examples" / "task.strict_production.yaml")

    with pytest.raises(ValueError) as exc:
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.strict_production.yaml"))

    assert "forbids local codegen endpoints" in str(exc.value)


def test_extract_codegen_payload_requires_provenance_in_strict_production() -> None:
    state = PipelineState(task_id="t1", status=TaskStatus.EXECUTING)
    action = Action(id="a1", action_type="llm_codegen", params={})
    result = ActionResult(
        action_id="a1",
        status="success",
        summary=Summary(step_id="a1", content="ok"),
        output={
            "endpoint": "https://api.example.com/v1/generate",
            "response": {
                "request_id": "req-1",
                "patches": [{"path": "src/a.txt", "mode": "overwrite", "content": "x"}],
            },
        },
    )
    record = ExecutionRecord(
        step_id=1,
        action=action,
        policy_result=PolicyResult(decision=PolicyDecision.ALLOW, reason="ok"),
        result=result,
    )
    state.add_record(record)
    outcome = RuntimeOutcome(status=TaskStatus.COMPLETED, state=state, message="done")

    runtime = RuntimeConfig(strict_production_mode=True)
    with pytest.raises(ValueError) as exc:
        _extract_codegen_payload(outcome, runtime)

    assert "requires llm response provenance fields" in str(exc.value)


def test_extract_codegen_payload_accepts_valid_provenance_in_strict_production() -> None:
    state = PipelineState(task_id="t1", status=TaskStatus.EXECUTING)
    action = Action(id="a1", action_type="llm_codegen", params={})
    result = ActionResult(
        action_id="a1",
        status="success",
        summary=Summary(step_id="a1", content="ok"),
        output={
            "endpoint": "https://api.example.com/v1/generate",
            "response": {
                "request_id": "req-1",
                "patches": [{"path": "src/a.txt", "mode": "overwrite", "content": "x"}],
                "provenance": {
                    "provider": "openai",
                    "model": "gpt-4.1",
                    "response_id": "resp_123",
                    "generated_by": "api_remote_agent",
                },
            },
        },
    )
    record = ExecutionRecord(
        step_id=1,
        action=action,
        policy_result=PolicyResult(decision=PolicyDecision.ALLOW, reason="ok"),
        result=result,
    )
    state.add_record(record)
    outcome = RuntimeOutcome(status=TaskStatus.COMPLETED, state=state, message="done")

    runtime = RuntimeConfig(strict_production_mode=True)
    request_id, patches, origin = _extract_codegen_payload(outcome, runtime)
    assert request_id == "req-1"
    assert patches and patches[0]["path"] == "src/a.txt"
    assert origin["provider"] == "openai"


def test_runtime_schema_exposes_strict_production_mode() -> None:
    config = load_full_config("configs")
    assert isinstance(config.runtime.strict_production_mode, bool)


