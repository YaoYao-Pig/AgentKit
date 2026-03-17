from pathlib import Path

from agentkit.starter.clean import clean_project


def test_clean_runtime_scope_removes_agentkit_dir(tmp_path: Path) -> None:
    target = tmp_path / "legacy"
    state_file = target / ".agentkit" / "state" / "task.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{}", encoding="utf-8")

    result = clean_project(target_dir=target, scope="runtime", dry_run=False)

    assert any(path.endswith(".agentkit") for path in result.removed_paths)
    assert not (target / ".agentkit").exists()


def test_clean_docs_scope_keeps_gitkeep(tmp_path: Path) -> None:
    target = tmp_path / "legacy"
    generated = target / "docs" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / ".gitkeep").write_text("", encoding="utf-8")
    (generated / "task_model.md").write_text("old", encoding="utf-8")

    clean_project(target_dir=target, scope="docs", dry_run=False)

    assert (generated / ".gitkeep").exists()
    assert not (generated / "task_model.md").exists()


def test_clean_all_dry_run_does_not_delete(tmp_path: Path) -> None:
    target = tmp_path / "legacy"
    (target / ".agentkit").mkdir(parents=True, exist_ok=True)
    (target / "README.starter.md").write_text("sidecar", encoding="utf-8")
    report = target / "docs" / "MIGRATION_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("report", encoding="utf-8")

    result = clean_project(target_dir=target, scope="all", dry_run=True)

    assert (target / ".agentkit").exists()
    assert (target / "README.starter.md").exists()
    assert report.exists()
    assert len(result.removed_paths) >= 3
