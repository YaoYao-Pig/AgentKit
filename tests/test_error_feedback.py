from pathlib import Path

import pytest

from agentkit.runner.api import run_task
from agentkit.runner.error_feedback import adopt_rules_from_report, load_latest_error_report
from agentkit.starter.init import initialize_starter_project


def _write_runtime_config(path: Path, *, default_action_type: str, strict: bool, healthcheck: bool) -> None:
    path.write_text(
        "\n".join(
            [
                "max_steps: 6",
                f"default_action_type: {default_action_type}",
                "api_host: 127.0.0.1",
                "api_port: 8787",
                "require_api_token: false",
                "api_token: dev-agentkit-token",
                "api_log_level: INFO",
                "api_log_to_file: true",
                "api_log_file: .agentkit/logs/agentkit-serve.log",
                f"strict_codegen_mode: {'true' if strict else 'false'}",
                f"llm_healthcheck_required: {'true' if healthcheck else 'false'}",
                "llm_endpoint_timeout_sec: 2",
                "llm_api_key_env: AGENTKIT_LLM_API_KEY",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_task_failure_writes_error_report(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    initialize_starter_project(target_dir=workspace, project_name="ErrorDemo", profile_name="minimal", force=True)

    _write_runtime_config(
        workspace / "configs" / "runtime.yaml",
        default_action_type="mock_action",
        strict=True,
        healthcheck=False,
    )

    with pytest.raises(ValueError) as exc:
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.sample.yaml"))

    message = str(exc.value)
    assert "error report:" in message
    report_path = Path(message.split("error report:", 1)[1].strip())
    assert report_path.exists()

    report = load_latest_error_report(workspace, "sample-task-001")
    assert report is not None
    assert report.events


def test_adopt_block_rule_can_prevent_repeat_missing_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "project"
    initialize_starter_project(target_dir=workspace, project_name="ErrorDemo", profile_name="minimal", force=True)

    _write_runtime_config(
        workspace / "configs" / "runtime.yaml",
        default_action_type="llm_codegen",
        strict=True,
        healthcheck=False,
    )
    monkeypatch.delenv("AGENTKIT_LLM_API_KEY", raising=False)

    with pytest.raises(ValueError):
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.codegen.sample.yaml"))

    report = load_latest_error_report(workspace, "sample-codegen-001")
    assert report is not None
    added, path = adopt_rules_from_report(workspace, report, [1], mode="block", note="block missing key")
    assert added == 1
    assert path.exists()

    with pytest.raises(ValueError) as exc:
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.codegen.sample.yaml"))

    assert "blocked by persisted avoidance rules" in str(exc.value)

