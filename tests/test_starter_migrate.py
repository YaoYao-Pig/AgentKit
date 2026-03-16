from pathlib import Path

from agentkit.starter.migrate import migrate_existing_project


def test_migrate_existing_project_creates_sidecars_and_report(tmp_path: Path) -> None:
    target = tmp_path / "legacy"
    target.mkdir(parents=True, exist_ok=True)

    # Simulate existing project files that should be preserved.
    (target / "README.md").write_text("legacy readme", encoding="utf-8")
    (target / "AGENTS.md").write_text("legacy agents", encoding="utf-8")
    (target / "configs").mkdir(parents=True, exist_ok=True)
    (target / "configs" / "module_rules.yaml").write_text("allowed_paths: [legacy/]\n", encoding="utf-8")
    (target / "docs" / "templates").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "templates" / "handoff_note.md").write_text("legacy template", encoding="utf-8")

    result = migrate_existing_project(target, project_name="LegacyProj", profile_name="minimal", create_sidecars=True)

    assert (target / "README.md").read_text(encoding="utf-8") == "legacy readme"
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "legacy agents"

    assert (target / "README.starter.md").exists()
    assert (target / "AGENTS.starter.md").exists()
    assert (target / "configs" / "module_rules.starter.yaml").exists()
    assert (target / "docs" / "templates" / "handoff_note.starter.md").exists()

    report = target / "docs" / "MIGRATION_REPORT.md"
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "safe migration" in content
    assert "README.starter.md" in content

    assert result.sidecar_paths
    assert result.report_path.endswith("MIGRATION_REPORT.md")
