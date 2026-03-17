from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import logging

from agentkit.config.loader import load_full_config
from agentkit.docs.bootstrap import load_registry_from_templates
from agentkit.docs.fill_engine import RuntimeDocumentInput, create_default_fill_engine
from agentkit.docs.renderer import TokenRenderer
from agentkit.docs.service import DocumentService
from agentkit.docs.template_loader import MarkdownTemplateLoader
from agentkit.docs.writer import DocumentWriter
from agentkit.runtime.context_selector import ContextSelectionRequest, ContextSelector
from agentkit.runtime.dispatcher import SkillDispatcherExecutor
from agentkit.runtime.engine import DefaultPipelineEngine
from agentkit.runtime.layers.capability import StaticCapabilityRegistry
from agentkit.runtime.layers.identity import StaticIdentityProvider
from agentkit.runtime.layers.planning import MinimalPlanner
from agentkit.runtime.layers.state import AutoApproveReviewHook, InMemoryStateStore
from agentkit.runtime.layers.validation import SimpleValidator
from agentkit.runtime.models import RuntimeOutcome, Task

from .guards import enforce_strict_codegen
from .task_spec import TaskRunSpec, load_task_run_spec


logger = logging.getLogger("agentkit.pipeline")


@dataclass(slots=True)
class TaskRunResult:
    task_id: str
    status: str
    state_path: str
    run_report_path: str
    context_report_path: str
    generated_docs: list[str]


def _json_default(obj: object) -> object:
    if hasattr(obj, "value"):
        return getattr(obj, "value")
    return str(obj)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _to_task(spec: TaskRunSpec) -> Task:
    return Task(
        id=spec.id,
        title=spec.title,
        goal=spec.goal,
        constraints=spec.constraints,
        success_criteria=spec.success_criteria,
        input_sources=spec.input_sources,
    )


def _task_spec_metadata(spec: TaskRunSpec) -> dict[str, object]:
    return {
        "affected_files": spec.affected_files,
        "validation_checklist": spec.validation_checklist,
        "rollback_plan": spec.rollback_plan,
        "risk_points": spec.risk_points,
        "module_hints": spec.module_hints,
        "action_type": spec.action_type,
    }


def _build_engine(workspace: Path, spec: TaskRunSpec, config) -> DefaultPipelineEngine:
    planner = MinimalPlanner(
        default_action_type=spec.action_type or config.runtime.default_action_type,
        default_action_params=spec.action_params,
    )
    return DefaultPipelineEngine(
        identity=StaticIdentityProvider(
            profile={"name": config.system_profile.agent_name, "role": config.system_profile.role}
        ),
        capability_registry=StaticCapabilityRegistry(action_types=list(config.skills_index.skills.keys())),
        planner=planner,
        executor=SkillDispatcherExecutor.from_skills_index(
            config.skills_index,
            workspace_root=str(workspace),
            allowed_paths=config.module_rules.allowed_paths,
        ),
        validator=SimpleValidator(
            blocked_action_types=set(config.policy_rules.blocked_action_types),
            review_action_types=set(config.policy_rules.review_action_types),
            allowed_paths=list(config.module_rules.allowed_paths),
        ),
        state_store=InMemoryStateStore(),
        review_hook=AutoApproveReviewHook(approve=True),
        max_steps=config.runtime.max_steps,
    )


def _write_context_report(workspace: Path, spec: TaskRunSpec) -> str:
    selector = ContextSelector(max_chars_per_file=1600)
    result = selector.select(
        ContextSelectionRequest(
            base_dir=str(workspace),
            task_type="runtime_task",
            goal=spec.goal,
            module_hints=spec.module_hints,
            max_chars=12000,
            include_generated_docs=True,
        )
    )

    out_dir = workspace / ".agentkit" / "context"
    _ensure_dir(out_dir)
    out_path = out_dir / f"{spec.id}.json"
    payload = {
        "task_id": spec.id,
        "goal": spec.goal,
        "total_chars": result.total_chars,
        "selected": [asdict(item) for item in result.selected],
        "omitted": result.omitted,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def _write_state(workspace: Path, outcome: RuntimeOutcome) -> str:
    out_dir = workspace / ".agentkit" / "state"
    _ensure_dir(out_dir)
    out_path = out_dir / f"{outcome.state.task_id}.json"
    out_path.write_text(json.dumps(asdict(outcome.state), ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return str(out_path)


def _update_docs(workspace: Path, task: Task, outcome: RuntimeOutcome) -> list[str]:
    generated_dir = workspace / "docs" / "generated"
    overrides = {
        "project_charter": str(generated_dir / "project_charter.md"),
        "task_model": str(generated_dir / "task_model.md"),
        "decision_log": str(generated_dir / "decision_log.md"),
        "risk_register": str(generated_dir / "risk_register.md"),
        "milestone_report": str(generated_dir / "milestone_report.md"),
        "handoff_note": str(generated_dir / "handoff_note.md"),
    }
    registry = load_registry_from_templates(str(workspace / "docs" / "templates"), output_path_overrides=overrides)
    service = DocumentService(
        registry=registry,
        loader=MarkdownTemplateLoader(),
        renderer=TokenRenderer(strict=True),
        writer=DocumentWriter(),
    )
    fill_engine = create_default_fill_engine(registry, service)

    payload = RuntimeDocumentInput(task=task, state=outcome.state)
    docs: list[str] = []
    for trigger in ["task_modeling", "postcheck", "task_completed"]:
        for result in fill_engine.update_for_trigger(trigger, payload):
            docs.append(result.output_path)
    return sorted(set(docs))


def _write_run_report(workspace: Path, spec: TaskRunSpec, outcome: RuntimeOutcome, docs: list[str], context_path: str) -> str:
    out_dir = workspace / ".agentkit" / "runs"
    _ensure_dir(out_dir)
    out_path = out_dir / f"{spec.id}.json"

    payload = {
        "task_id": spec.id,
        "goal": spec.goal,
        "status": outcome.status.value,
        "records": len(outcome.state.records),
        "retries": outcome.state.retries,
        "context_report": context_path,
        "generated_docs": docs,
        "affected_files": spec.affected_files,
        "validation_checklist": spec.validation_checklist,
        "rollback_plan": spec.rollback_plan,
        "risk_points": spec.risk_points,
        "strict_codegen_mode": bool(outcome.state.metadata.get("strict_codegen_mode", False)),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def run_task(workspace: str, task_file: str) -> TaskRunResult:
    workspace_path = Path(workspace).resolve()
    spec_path = Path(task_file)
    if not spec_path.is_absolute():
        spec_path = workspace_path / spec_path
    spec = load_task_run_spec(str(spec_path))

    config = load_full_config(str(workspace_path / "configs"))
    enforce_strict_codegen(config, spec)

    logger.info(
        "task run started task_id=%s action_type=%s strict_codegen=%s workspace=%s",
        spec.id,
        spec.action_type or config.runtime.default_action_type,
        config.runtime.strict_codegen_mode,
        workspace_path,
    )

    context_report = _write_context_report(workspace_path, spec)
    engine = _build_engine(workspace_path, spec, config)
    task = _to_task(spec)
    outcome = engine.run(task)

    outcome.state.metadata["workspace_root"] = str(workspace_path)
    outcome.state.metadata["module_rules"] = asdict(config.module_rules)
    outcome.state.metadata["task_spec"] = _task_spec_metadata(spec)
    outcome.state.metadata["strict_codegen_mode"] = config.runtime.strict_codegen_mode

    state_path = _write_state(workspace_path, outcome)
    docs = _update_docs(workspace_path, task, outcome)
    run_report = _write_run_report(workspace_path, spec, outcome, docs, context_report)

    logger.info(
        "task run completed task_id=%s status=%s records=%d retries=%d",
        spec.id,
        outcome.status.value,
        len(outcome.state.records),
        outcome.state.retries,
    )

    return TaskRunResult(
        task_id=spec.id,
        status=outcome.status.value,
        state_path=state_path,
        run_report_path=run_report,
        context_report_path=context_report,
        generated_docs=docs,
    )


def verify_task_run(workspace: str, task_id: str) -> tuple[bool, list[str]]:
    base = Path(workspace).resolve()
    required = [
        base / ".agentkit" / "state" / f"{task_id}.json",
        base / ".agentkit" / "runs" / f"{task_id}.json",
        base / ".agentkit" / "context" / f"{task_id}.json",
        base / "docs" / "generated" / "task_model.md",
        base / "docs" / "generated" / "decision_log.md",
        base / "docs" / "generated" / "handoff_note.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    return (len(missing) == 0, missing)





