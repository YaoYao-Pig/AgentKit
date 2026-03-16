from pathlib import Path

from agentkit.runner.api import run_task, verify_task_run
from agentkit.starter.init import initialize_starter_project


def test_run_task_generates_required_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    initialize_starter_project(target_dir=workspace, project_name="RunnerDemo", profile_name="minimal", force=True)

    task_file = workspace / "examples" / "task.sample.yaml"
    result = run_task(workspace=str(workspace), task_file=str(task_file))

    assert result.status in {"COMPLETED", "FAILED"}
    assert Path(result.state_path).exists()
    assert Path(result.context_report_path).exists()
    assert Path(result.run_report_path).exists()
    assert result.generated_docs

    task_model = (workspace / "docs" / "generated" / "task_model.md").read_text(encoding="utf-8")
    assert "Affected Files/Modules" in task_model
    assert "Validation Checklist" in task_model
    assert "Rollback Plan" in task_model
    assert "Risk Points" in task_model

    ok, missing = verify_task_run(workspace=str(workspace), task_id="sample-task-001")
    assert ok, f"missing artifacts: {missing}"
