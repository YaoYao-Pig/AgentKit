from pathlib import Path

import pytest

from agentkit.runner.env_check import ensure_workspace_environment, inspect_environment


def test_inspect_environment_flags_shadowed_module(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    (workspace / "src" / "agentkit").mkdir(parents=True, exist_ok=True)

    report = inspect_environment(str(workspace))

    assert report.workspace_has_local_source is True
    assert report.module_under_workspace_source is False
    assert report.is_valid is False
    assert report.issues


def test_ensure_workspace_environment_raises_on_shadowed_module(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    (workspace / "src" / "agentkit").mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError) as exc:
        ensure_workspace_environment(str(workspace))

    assert "environment check failed" in str(exc.value)
