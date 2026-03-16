from pathlib import Path

import yaml

from agentkit.starter.apply import apply_starter_project


def test_apply_starter_project_with_spec(tmp_path: Path) -> None:
    target = tmp_path / "apply_demo"
    spec = tmp_path / "apply_spec.yaml"
    spec.write_text(
        yaml.safe_dump(
            {
                "configs": {
                    "module_rules": {
                        "allowed_paths": ["src/", "docs/"],
                        "disallowed_dependencies": [{"from": "a", "to": "b"}],
                    }
                },
                "templates": {
                    "handoff_note": {
                        "metadata": {"output_path": "docs/generated/custom_handoff.md"},
                        "body_append": "## Extra\n- hello",
                    }
                },
                "docs": {"regenerate": True},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = apply_starter_project(
        target_dir=target,
        project_name="Apply Demo",
        profile_name="minimal",
        spec_path=spec,
        force=True,
    )

    assert result.spec_path == str(spec)
    module_rules = yaml.safe_load((target / "configs" / "module_rules.yaml").read_text(encoding="utf-8"))
    assert module_rules["allowed_paths"] == ["src/", "docs/"]

    handoff_template = (target / "docs" / "templates" / "handoff_note.md").read_text(encoding="utf-8")
    assert "custom_handoff.md" in handoff_template
    assert "## Extra" in handoff_template

    generated = list((target / "docs" / "generated").glob("*.md"))
    assert generated
