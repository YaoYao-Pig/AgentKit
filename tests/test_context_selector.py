from pathlib import Path

from agentkit.runtime.context_selector import ContextSelectionRequest, ContextSelector


def test_context_selector_picks_core_files_with_budget(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir(parents=True)
    (tmp_path / "docs" / "generated").mkdir(parents=True)
    (tmp_path / "src" / "project").mkdir(parents=True)

    (tmp_path / "AGENTS.md").write_text("protocol", encoding="utf-8")
    (tmp_path / "configs" / "policy_rules.yaml").write_text("blocked: []", encoding="utf-8")
    (tmp_path / "configs" / "module_rules.yaml").write_text("allowed: [src/]", encoding="utf-8")
    (tmp_path / "configs" / "skills_index.yaml").write_text("skills: {}", encoding="utf-8")
    (tmp_path / "configs" / "runtime.yaml").write_text("max_steps: 5", encoding="utf-8")
    (tmp_path / "docs" / "generated" / "task_model.md").write_text("task model", encoding="utf-8")
    (tmp_path / "src" / "project" / "billing_service.py").write_text("def x():\n    pass", encoding="utf-8")

    selector = ContextSelector(max_chars_per_file=200)
    result = selector.select(
        ContextSelectionRequest(
            base_dir=str(tmp_path),
            task_type="feature",
            goal="update billing",
            module_hints=["billing"],
            max_chars=600,
        )
    )

    assert result.total_chars <= 600
    paths = [item.path for item in result.selected]
    assert any(path.endswith("AGENTS.md") for path in paths)
    assert any("billing_service.py" in path for path in paths)


def test_context_selector_can_skip_generated_docs(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir(parents=True)
    (tmp_path / "docs" / "generated").mkdir(parents=True)

    (tmp_path / "configs" / "policy_rules.yaml").write_text("x: 1", encoding="utf-8")
    (tmp_path / "configs" / "module_rules.yaml").write_text("x: 1", encoding="utf-8")
    (tmp_path / "configs" / "skills_index.yaml").write_text("x: 1", encoding="utf-8")
    (tmp_path / "configs" / "runtime.yaml").write_text("x: 1", encoding="utf-8")
    (tmp_path / "docs" / "generated" / "decision_log.md").write_text("decision", encoding="utf-8")

    selector = ContextSelector(max_chars_per_file=200)
    result = selector.select(
        ContextSelectionRequest(
            base_dir=str(tmp_path),
            task_type="fix",
            goal="quick fix",
            include_generated_docs=False,
            max_chars=500,
        )
    )

    assert all("docs\\generated" not in item.path and "docs/generated" not in item.path for item in result.selected)
