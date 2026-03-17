from pathlib import Path

from agentkit.docs.bootstrap import load_registry_from_templates
from agentkit.docs.models import DEFAULT_DOCUMENT_TYPES


def test_registry_loading_from_templates() -> None:
    registry = load_registry_from_templates("docs/templates")
    ids = registry.list_ids()
    for required in DEFAULT_DOCUMENT_TYPES:
        assert required in ids


def test_registry_supports_output_override() -> None:
    registry = load_registry_from_templates(
        "docs/templates",
        output_path_overrides={"handoff_note": "docs/generated/custom_handoff.md"},
    )
    definition = registry.get("handoff_note")
    assert definition.resolved_output_path.endswith("custom_handoff.md")


def test_registry_ignores_starter_sidecar_templates(tmp_path: Path) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    main_template = template_dir / "decision_log.md"
    sidecar_template = template_dir / "decision_log.starter.md"

    content = """---
id: decision_log
title: Decision Log
purpose: Track decisions
owner_agent: planner
created_when: task_modeling
updated_when: postcheck
input_sources: []
render_strategy: token_v1
write_strategy: append
output_path: docs/generated/decision_log.md
---
# Decision Log
"""
    main_template.write_text(content, encoding="utf-8")
    sidecar_template.write_text(content, encoding="utf-8")

    registry = load_registry_from_templates(str(template_dir))
    assert registry.list_ids() == ["decision_log"]
