from pathlib import Path

from agentkit.starter.init import initialize_starter_project


def test_initialize_minimal_profile(tmp_path: Path) -> None:
    target = tmp_path / "demo_minimal"
    result = initialize_starter_project(target_dir=target, project_name="Demo Minimal", profile_name="minimal")

    assert result.profile == "minimal"
    for rel in [
        "src/agentkit/runtime",
        "configs",
        "docs/templates",
        "docs/generated",
        "skills",
        "examples",
        "tests",
    ]:
        assert (target / rel).exists()

    assert (target / "README.md").exists()
    assert (target / "src" / "agentkit" / "runner" / "api.py").exists()
    assert (target / "src" / "agentkit" / "starter" / "init.py").exists()
    assert (target / ".github" / "workflows" / "agentkit-ci.yml").exists()
    assert (target / "examples" / "task.sample.yaml").exists()
    assert (target / "examples" / "api_enforced_demo.py").exists()
    assert (target / "examples" / "task.codegen.sample.yaml").exists()
    assert (target / "AGENTS.md").exists()
    assert (target / "docs" / "CUSTOMIZATION.md").exists()

    assert (target / "docs" / "generated" / "project_charter.md").exists()
    assert (target / "docs" / "generated" / "task_model.md").exists()
    assert (target / "docs" / "generated" / "decision_log.md").exists()
    assert (target / "docs" / "generated" / "handoff_note.md").exists()
    assert list((target / "docs" / "generated").glob("milestone_report.v*.md"))
    assert list((target / "docs" / "generated").glob("risk_register.*.md"))


def test_initialize_extended_profile_adds_customization_example(tmp_path: Path) -> None:
    target = tmp_path / "demo_extended"
    result = initialize_starter_project(target_dir=target, project_name="Demo Extended", profile_name="extended")

    assert result.profile == "extended"
    assert (target / "examples" / "customize_starter.py").exists()


def test_initialize_respects_force_flag(tmp_path: Path) -> None:
    target = tmp_path / "demo_force"
    target.mkdir(parents=True, exist_ok=True)
    readme = target / "README.md"
    readme.write_text("custom", encoding="utf-8")

    initialize_starter_project(target_dir=target, project_name="Force Demo", profile_name="minimal", force=False)
    assert readme.read_text(encoding="utf-8") == "custom"

    initialize_starter_project(target_dir=target, project_name="Force Demo", profile_name="minimal", force=True)
    assert "Force Demo" in readme.read_text(encoding="utf-8")



