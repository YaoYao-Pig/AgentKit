from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2

from agentkit.docs.bootstrap import load_registry_from_templates
from agentkit.docs.fill_engine import RuntimeDocumentInput, create_default_fill_engine
from agentkit.docs.renderer import TokenRenderer
from agentkit.docs.service import DocumentService
from agentkit.docs.template_loader import MarkdownTemplateLoader
from agentkit.docs.writer import DocumentWriter
from agentkit.runtime.models import PipelineState, Summary, Task, TaskStatus

from .profiles import PROFILES


@dataclass(slots=True)
class InitResult:
    project_name: str
    profile: str
    target_dir: str
    generated_paths: list[str]


ROOT_README_TEMPLATE = """# {project_name}

This project was bootstrapped from AgentKit starter.

## Quick Start

```bash
pip install -e .
python -m pytest
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001

# optional: API-enforced mode
agentkit-serve --workspace . --require-token --token dev-agentkit-token
```

## Project Layout

- `src/agentkit/`: reusable runtime + docs + config framework modules
- `configs/`: runtime, policy, module, and skills configuration
- `docs/templates/`: reusable document templates
- `docs/generated/`: generated project documents
- `skills/`: local skill definitions
- `examples/`: starter runtime/document examples
- `tests/`: baseline validation tests

## Customization

See `docs/CUSTOMIZATION.md` for module rule, skills, and template customization.
"""

ROOT_AGENTS_TEMPLATE = """# AGENTS.md

## Mission
This repository is a reusable agent pipeline project scaffold.

## Working Rules
- Keep runtime, config, and document systems decoupled.
- Prefer typed schemas over free-form dictionaries.
- Keep policy, skill, storage, and renderer layers pluggable.
- Avoid domain-specific business logic in core runtime.

## Mandatory Execution Protocol
1. Read and comply with:
   - AGENTS.md
   - configs/policy_rules.yaml
   - configs/module_rules.yaml
   - configs/skills_index.yaml
2. Before edits, provide:
   - task model
   - impacted scope
   - risk points
3. Run validation pre-check and post-check for each action.
4. Update docs/generated at least:
   - task_model
   - decision_log
   - handoff_note
5. For destructive/high-risk actions, request human approval first.
6. Task execution must enter via `agentkit-run` or `python -m agentkit run --task ...` before business-code edits.
7. If API mode is enabled, tasks must be triggered through `agentkit-serve` endpoints with valid token.
8. Final output must include:
   - changed files
   - evidence references
   - remaining risks/todos

## Customization Targets
- `configs/module_rules.yaml`
- `configs/skills_index.yaml`
- `docs/templates/*.md`
- `src/agentkit/runtime/layers/*`
"""

CUSTOMIZATION_DOC = """# Downstream Customization Guide

## 1) Module Rules
Edit `configs/module_rules.yaml`:
- define allowed paths
- define forbidden dependency directions

## 2) Skills
Edit `configs/skills_index.yaml`:
- register local skills
- declare purpose/risk level

## 3) Document Templates
Edit files in `docs/templates/`:
- metadata controls ownership and lifecycle triggers
- body controls markdown output using `{{token}}`

## 4) Output Paths
Override output paths during registry loading (code example in `examples/customize_starter.py`).

## 5) Tool Adapters and Skills
Edit `configs/skills_index.yaml` to bind action types to adapters (`mock`, `shell`, `python_callable`, `llm_http`, `file_patch`).
- shell skills use `command` templates
- python_callable skills use `module` + `function`
- llm_http skills call your model gateway and return structured JSON
- file_patch skills apply controlled writes from structured patch lists

## 6) API Enforcement
Edit `configs/runtime.yaml`:
- `require_api_token`: force token auth for API calls
- `api_token`: token value used by `agentkit-serve`
- `api_host` / `api_port`: bind address
"""

CUSTOMIZE_EXAMPLE = """from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentkit.docs.bootstrap import load_registry_from_templates


def main() -> None:
    overrides = {
        "handoff_note": "docs/generated/team_handoff.md",
        "milestone_report": "docs/generated/releases/milestone.md",
    }
    registry = load_registry_from_templates("docs/templates", output_path_overrides=overrides)
    print("Customized output paths:")
    for doc_id in registry.list_ids():
        definition = registry.get(doc_id)
        print(f"- {doc_id}: {definition.resolved_output_path}")


if __name__ == "__main__":
    main()
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path, force: bool) -> bool:
    if dst.exists() and not force:
        return False
    _ensure_dir(dst.parent)
    copy2(src, dst)
    return True


def _copy_tree_files(src_dir: Path, dst_dir: Path, force: bool) -> list[Path]:
    generated: list[Path] = []
    for src in sorted(src_dir.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        if _copy_file(src, dst, force=force):
            generated.append(dst)
    return generated


def _render_text_file(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    _ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return True


def _generate_default_docs(target_dir: Path) -> list[Path]:
    template_dir = target_dir / "docs" / "templates"
    generated_dir = target_dir / "docs" / "generated"
    overrides = {
        "project_charter": str(generated_dir / "project_charter.md"),
        "task_model": str(generated_dir / "task_model.md"),
        "decision_log": str(generated_dir / "decision_log.md"),
        "risk_register": str(generated_dir / "risk_register.md"),
        "milestone_report": str(generated_dir / "milestone_report.md"),
        "handoff_note": str(generated_dir / "handoff_note.md"),
    }
    registry = load_registry_from_templates(str(template_dir), output_path_overrides=overrides)
    service = DocumentService(
        registry=registry,
        loader=MarkdownTemplateLoader(),
        renderer=TokenRenderer(strict=True),
        writer=DocumentWriter(),
    )
    fill_engine = create_default_fill_engine(registry, service)

    task = Task(
        id="starter-init-task",
        title="Bootstrap starter project",
        goal="Generate baseline runtime documents",
        constraints=["Keep framework reusable", "Keep configuration pluggable"],
        success_criteria=["Starter docs generated"],
        input_sources=["configs/", "docs/templates/"],
    )
    state = PipelineState(task_id=task.id, status=TaskStatus.COMPLETED, current_phase="delivery")
    state.summaries.append(Summary(step_id="init", content="Starter initialization completed"))

    payload = RuntimeDocumentInput(task=task, state=state)
    generated: list[Path] = []
    for trigger in ["task_modeling", "postcheck", "task_completed"]:
        for result in fill_engine.update_for_trigger(trigger, payload):
            generated.append(Path(result.output_path))
    return generated


def initialize_starter_project(
    target_dir: Path,
    project_name: str,
    profile_name: str = "minimal",
    force: bool = False,
    generate_default_docs: bool = True,
) -> InitResult:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name}")
    profile = PROFILES[profile_name]
    root = _repo_root()

    generated: list[Path] = []
    _ensure_dir(target_dir)

    required_dirs = [
        target_dir / "src" / "agentkit",
        target_dir / "configs",
        target_dir / "docs" / "templates",
        target_dir / "docs" / "generated",
        target_dir / "skills",
        target_dir / "examples",
        target_dir / "tests",
        target_dir / ".github" / "workflows",
    ]
    for directory in required_dirs:
        _ensure_dir(directory)
        generated.append(directory)

    generated.extend(
        _copy_tree_files(root / "src" / "agentkit" / "runtime", target_dir / "src" / "agentkit" / "runtime", force)
    )
    generated.extend(
        _copy_tree_files(root / "src" / "agentkit" / "docs", target_dir / "src" / "agentkit" / "docs", force)
    )
    generated.extend(
        _copy_tree_files(root / "src" / "agentkit" / "config", target_dir / "src" / "agentkit" / "config", force)
    )
    generated.extend(
        _copy_tree_files(root / "src" / "agentkit" / "runner", target_dir / "src" / "agentkit" / "runner", force)
    )

    for file_name in ["__init__.py", "__main__.py"]:
        if _copy_file(root / "src" / "agentkit" / file_name, target_dir / "src" / "agentkit" / file_name, force):
            generated.append(target_dir / "src" / "agentkit" / file_name)

    for file_name in [
        "system_profile.yaml",
        "skills_index.yaml",
        "policy_rules.yaml",
        "module_rules.yaml",
        "runtime.yaml",
    ]:
        if _copy_file(root / "configs" / file_name, target_dir / "configs" / file_name, force):
            generated.append(target_dir / "configs" / file_name)

    for file_name in [
        "project_charter.md",
        "task_model.md",
        "decision_log.md",
        "risk_register.md",
        "milestone_report.md",
        "handoff_note.md",
    ]:
        if _copy_file(root / "docs" / "templates" / file_name, target_dir / "docs" / "templates" / file_name, force):
            generated.append(target_dir / "docs" / "templates" / file_name)

    for example_name in ["mock_pipeline.py", "task.sample.yaml", "task.codegen.sample.yaml", "context_selection_demo.py", "api_enforced_demo.py", "apply_spec.yaml"]:
        if _copy_file(root / "examples" / example_name, target_dir / "examples" / example_name, force):
            generated.append(target_dir / "examples" / example_name)

    if profile.include_extra_example:
        if _render_text_file(target_dir / "examples" / "customize_starter.py", CUSTOMIZE_EXAMPLE, force):
            generated.append(target_dir / "examples" / "customize_starter.py")

    if profile.include_tests:
        for file_name in [
            "test_schema_validation.py",
            "test_registry_loading.py",
            "test_document_rendering.py",
            "test_fill_engine.py",
            "test_runtime_happy_path.py",
            "test_runtime_replan_branch.py",
            "test_runtime_dispatcher.py",
            "test_context_selector.py",
            "test_runner_pipeline.py",
            "test_runner_api_server.py",
            "test_runtime_codegen_flow.py",
        ]:
            if _copy_file(root / "tests" / file_name, target_dir / "tests" / file_name, force):
                generated.append(target_dir / "tests" / file_name)

    if _copy_file(root / "pyproject.toml", target_dir / "pyproject.toml", force):
        generated.append(target_dir / "pyproject.toml")
    if _copy_file(root / ".gitignore", target_dir / ".gitignore", force):
        generated.append(target_dir / ".gitignore")

    workflow_src = root / ".github" / "workflows" / "agentkit-ci.yml"
    workflow_dst = target_dir / ".github" / "workflows" / "agentkit-ci.yml"
    if workflow_src.exists() and _copy_file(workflow_src, workflow_dst, force):
        generated.append(workflow_dst)

    if _render_text_file(target_dir / "README.md", ROOT_README_TEMPLATE.format(project_name=project_name), force):
        generated.append(target_dir / "README.md")
    if _render_text_file(target_dir / "AGENTS.md", ROOT_AGENTS_TEMPLATE, force):
        generated.append(target_dir / "AGENTS.md")
    if _render_text_file(target_dir / "docs" / "CUSTOMIZATION.md", CUSTOMIZATION_DOC, force):
        generated.append(target_dir / "docs" / "CUSTOMIZATION.md")

    gitkeep = target_dir / "docs" / "generated" / ".gitkeep"
    if _render_text_file(gitkeep, "", force):
        generated.append(gitkeep)

    if generate_default_docs:
        generated.extend(_generate_default_docs(target_dir))

    unique_paths = sorted({str(path) for path in generated})
    return InitResult(
        project_name=project_name,
        profile=profile.name,
        target_dir=str(target_dir),
        generated_paths=unique_paths,
    )







