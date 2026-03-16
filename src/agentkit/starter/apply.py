from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agentkit.docs.bootstrap import load_registry_from_templates
from agentkit.docs.fill_engine import RuntimeDocumentInput, create_default_fill_engine
from agentkit.docs.renderer import TokenRenderer
from agentkit.docs.service import DocumentService
from agentkit.docs.template_loader import MarkdownTemplateLoader
from agentkit.docs.writer import DocumentWriter
from agentkit.runtime.models import PipelineState, Summary, Task, TaskStatus

from .init import InitResult, initialize_starter_project


@dataclass(slots=True)
class ApplyResult(InitResult):
    spec_path: str | None = None


@dataclass(slots=True)
class ApplySpec:
    configs: dict[str, dict[str, Any]]
    templates: dict[str, dict[str, Any]]
    regenerate_docs: bool


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("apply spec must be a YAML mapping")
    return data


def _parse_spec(path: Path | None) -> ApplySpec:
    if path is None:
        return ApplySpec(configs={}, templates={}, regenerate_docs=True)
    root = _load_yaml(path)
    configs = root.get("configs", {})
    templates = root.get("templates", {})
    docs = root.get("docs", {})
    if not isinstance(configs, dict) or not isinstance(templates, dict) or not isinstance(docs, dict):
        raise ValueError("invalid apply spec sections")
    regenerate_docs = bool(docs.get("regenerate", True))
    return ApplySpec(configs=configs, templates=templates, regenerate_docs=regenerate_docs)


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        raise ValueError("template must start with YAML front matter")
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("template front matter is malformed")
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        raise ValueError("template front matter must be mapping")
    body = parts[2].lstrip("\n")
    return metadata, body


def _serialize_template(metadata: dict[str, Any], body: str) -> str:
    meta = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=False).rstrip()
    return f"---\n{meta}\n---\n{body.rstrip()}\n"


def _apply_template_override(template_path: Path, override: dict[str, Any]) -> None:
    raw = template_path.read_text(encoding="utf-8")
    metadata, body = _split_front_matter(raw)

    metadata_updates = override.get("metadata", {})
    if metadata_updates:
        if not isinstance(metadata_updates, dict):
            raise ValueError("template metadata override must be mapping")
        metadata.update(metadata_updates)

    if "body" in override:
        body = str(override["body"])
    if "body_append" in override:
        body = f"{body.rstrip()}\n\n{str(override['body_append']).rstrip()}\n"

    template_path.write_text(_serialize_template(metadata, body), encoding="utf-8")


def _doc_output_overrides(target_dir: Path) -> dict[str, str]:
    generated_dir = target_dir / "docs" / "generated"
    return {
        "project_charter": str(generated_dir / "project_charter.md"),
        "task_model": str(generated_dir / "task_model.md"),
        "decision_log": str(generated_dir / "decision_log.md"),
        "risk_register": str(generated_dir / "risk_register.md"),
        "milestone_report": str(generated_dir / "milestone_report.md"),
        "handoff_note": str(generated_dir / "handoff_note.md"),
    }


def _regenerate_docs(target_dir: Path) -> list[Path]:
    generated_dir = target_dir / "docs" / "generated"
    for file in generated_dir.glob("*.md"):
        file.unlink()

    registry = load_registry_from_templates(
        str(target_dir / "docs" / "templates"),
        output_path_overrides=_doc_output_overrides(target_dir),
    )
    service = DocumentService(
        registry=registry,
        loader=MarkdownTemplateLoader(),
        renderer=TokenRenderer(strict=True),
        writer=DocumentWriter(),
    )
    fill_engine = create_default_fill_engine(registry, service)

    task = Task(
        id="starter-apply-task",
        title="Apply starter customization",
        goal="Generate project docs after customization",
        constraints=["Config-driven setup", "Template-based documents"],
        success_criteria=["Starter docs regenerated"],
        input_sources=["configs/", "docs/templates/"],
    )
    state = PipelineState(task_id=task.id, status=TaskStatus.COMPLETED, current_phase="delivery")
    state.summaries.append(Summary(step_id="apply", content="Starter apply completed"))

    payload = RuntimeDocumentInput(task=task, state=state)
    paths: list[Path] = []
    for trigger in ["task_modeling", "postcheck", "task_completed"]:
        for result in fill_engine.update_for_trigger(trigger, payload):
            paths.append(Path(result.output_path))
    return paths


def apply_starter_project(
    target_dir: Path,
    project_name: str,
    profile_name: str = "minimal",
    spec_path: Path | None = None,
    force: bool = False,
) -> ApplyResult:
    init_result = initialize_starter_project(
        target_dir=target_dir,
        project_name=project_name,
        profile_name=profile_name,
        force=force,
    )

    spec = _parse_spec(spec_path)
    changed: list[Path] = []

    config_allowed = {
        "system_profile",
        "skills_index",
        "policy_rules",
        "module_rules",
        "runtime",
    }
    for key, payload in spec.configs.items():
        if key not in config_allowed:
            raise ValueError(f"unsupported config override: {key}")
        if not isinstance(payload, dict):
            raise ValueError(f"config override '{key}' must be mapping")
        out = target_dir / "configs" / f"{key}.yaml"
        _write_yaml(out, payload)
        changed.append(out)

    if spec.templates:
        registry = load_registry_from_templates(
            str(target_dir / "docs" / "templates"),
            output_path_overrides=_doc_output_overrides(target_dir),
        )
        for doc_id, override in spec.templates.items():
            if not isinstance(override, dict):
                raise ValueError(f"template override '{doc_id}' must be mapping")
            definition = registry.get(doc_id)
            path = Path(definition.template_path)
            _apply_template_override(path, override)
            changed.append(path)

    if spec.regenerate_docs:
        changed.extend(_regenerate_docs(target_dir))

    all_paths = sorted({*init_result.generated_paths, *[str(p) for p in changed]})
    return ApplyResult(
        project_name=init_result.project_name,
        profile=init_result.profile,
        target_dir=init_result.target_dir,
        generated_paths=all_paths,
        spec_path=str(spec_path) if spec_path else None,
    )
