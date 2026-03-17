from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import logging
import subprocess

from agentkit.config.loader import load_full_config
from agentkit.docs.bootstrap import load_registry_from_templates
from agentkit.docs.fill_engine import RuntimeDocumentInput, create_default_fill_engine
from agentkit.docs.renderer import TokenRenderer
from agentkit.docs.service import DocumentService
from agentkit.docs.template_loader import MarkdownTemplateLoader
from agentkit.docs.writer import DocumentWriter
from agentkit.runtime.adapters.base import FilePatchAdapter
from agentkit.runtime.context_selector import ContextSelectionRequest, ContextSelector
from agentkit.runtime.dispatcher import SkillDispatcherExecutor
from agentkit.runtime.engine import DefaultPipelineEngine
from agentkit.runtime.layers.capability import StaticCapabilityRegistry
from agentkit.runtime.layers.identity import StaticIdentityProvider
from agentkit.runtime.layers.planning import MinimalPlanner
from agentkit.runtime.layers.state import AutoApproveReviewHook, InMemoryStateStore
from agentkit.runtime.layers.validation import SimpleValidator
from agentkit.runtime.models import Action, RuntimeOutcome, Task

from .error_feedback import build_report, evaluate_avoidance_rules, make_event, write_error_report
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
    error_report_path: str = ""


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


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_codegen_payload(outcome: RuntimeOutcome) -> tuple[str, list[dict[str, object]]]:
    if not outcome.state.records:
        raise ValueError("strict_codegen_mode expected at least one execution record")

    response = outcome.state.records[-1].result.output.get("response")
    if not isinstance(response, dict):
        raise ValueError("strict_codegen_mode expected llm response payload")

    request_id = str(response.get("request_id") or "").strip()
    if not request_id:
        raise ValueError("strict_codegen_mode requires llm response.request_id")

    patches = response.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("strict_codegen_mode requires llm response.patches (non-empty list)")

    normalized: list[dict[str, object]] = []
    for idx, item in enumerate(patches):
        if not isinstance(item, dict):
            raise ValueError(f"strict_codegen_mode patch[{idx}] must be an object")
        path = str(item.get("path") or "").strip()
        content = str(item.get("content") or "")
        mode = str(item.get("mode") or "overwrite").strip().lower()
        if not path:
            raise ValueError(f"strict_codegen_mode patch[{idx}] missing path")
        normalized.append({"path": path, "content": content, "mode": mode})

    return request_id, normalized


def _read_task_ledger(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _collect_all_touched_files(workspace: Path) -> set[str]:
    out_dir = workspace / ".agentkit" / "patches"
    if not out_dir.exists():
        return set()

    touched: set[str] = set()
    for ledger_path in sorted(out_dir.glob("*.json")):
        payload = _read_task_ledger(ledger_path)
        for item in payload.get("touched_files", []):
            touched.add(str(item).replace("\\", "/"))
    return touched


def _apply_generated_patches(workspace: Path, config, spec: TaskRunSpec, outcome: RuntimeOutcome) -> dict[str, object]:
    request_id, patches = _extract_codegen_payload(outcome)

    skill = config.skills_index.skills.get("apply_generated_patch")
    if skill is None:
        raise ValueError("strict_codegen_mode requires skill 'apply_generated_patch'")

    adapter = FilePatchAdapter(workspace_root=str(workspace), allowed_paths=config.module_rules.allowed_paths)
    action = Action(
        id=f"{spec.id}-apply-generated-patch",
        action_type="apply_generated_patch",
        params={"patches": patches},
    )
    result = adapter.execute(action, outcome.state, skill)
    if result.status != "success":
        raise ValueError(f"failed to apply generated patches: {result.output}")

    patch_entries: list[dict[str, object]] = []
    touched_files: list[str] = []
    for item in patches:
        rel_path = str(item["path"])
        abs_path = (workspace / rel_path).resolve()
        file_hash = _hash_file(abs_path) if abs_path.exists() else ""
        touched_files.append(rel_path.replace("\\", "/"))
        patch_entries.append(
            {
                "path": rel_path,
                "mode": item["mode"],
                "content_sha256": hashlib.sha256(str(item["content"]).encode("utf-8")).hexdigest(),
                "file_sha256": file_hash,
            }
        )

    out_dir = workspace / ".agentkit" / "patches"
    _ensure_dir(out_dir)
    out_path = out_dir / f"{spec.id}.json"

    previous = _read_task_ledger(out_path)
    previous_entries = previous.get("patches", []) if isinstance(previous.get("patches"), list) else []
    previous_touched = previous.get("touched_files", []) if isinstance(previous.get("touched_files"), list) else []
    previous_rounds = previous.get("rounds", []) if isinstance(previous.get("rounds"), list) else []

    round_index = len(previous_rounds) + 1
    round_entry = {
        "round": round_index,
        "request_id": request_id,
        "patch_count": len(patch_entries),
        "touched_files": sorted(set(touched_files)),
    }

    combined_entries = list(previous_entries) + patch_entries
    combined_touched = sorted(set(str(x).replace("\\", "/") for x in previous_touched + touched_files))
    ledger = {
        "task_id": spec.id,
        "request_id": request_id,
        "action_type": "llm_codegen",
        "patch_count": len(combined_entries),
        "patches": combined_entries,
        "touched_files": combined_touched,
        "rounds": previous_rounds + [round_entry],
    }
    out_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "strict codegen patches applied task_id=%s request_id=%s patches=%d rounds=%d",
        spec.id,
        request_id,
        len(patch_entries),
        len(ledger["rounds"]),
    )
    return {"ledger_path": str(out_path), "request_id": request_id, "touched_files": ledger["touched_files"]}


def _collect_outcome_error_events(outcome: RuntimeOutcome) -> list:
    events = []
    for record in outcome.state.records:
        if record.result.status == "failed":
            message = str(record.result.output.get("message") or record.result.summary.content or "action failed")
            events.append(make_event(message, stage="execution", action_type=record.action.action_type))
    return events


def _persist_exception_report(workspace: Path, task_id: str, exc: Exception, action_type: str) -> str:
    event = make_event(str(exc), stage="run_task", action_type=action_type)
    report = build_report(task_id=task_id, events=[event])
    return str(write_error_report(workspace, report))


def _write_run_report(
    workspace: Path,
    spec: TaskRunSpec,
    outcome: RuntimeOutcome,
    docs: list[str],
    context_path: str,
    error_report_path: str,
) -> str:
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
        "strict_industrial_mode": bool(outcome.state.metadata.get("strict_industrial_mode", False)),
        "patch_ledger": outcome.state.metadata.get("patch_ledger"),
        "patch_request_id": outcome.state.metadata.get("patch_request_id"),
        "error_report": error_report_path,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def _is_git_repo(workspace: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0 and completed.stdout.strip().lower() == "true"


def _git_changed_files(workspace: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(workspace), "status", "--porcelain", "--untracked-files=all"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []

    if completed.returncode != 0:
        return []

    changed: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if not path:
            continue
        changed.append(path.replace("\\", "/"))
    return sorted(set(changed))


def _manual_edit_violations(
    workspace: Path,
    protected_prefixes: list[str],
    allowed_touched_files: set[str],
) -> list[str]:
    violations: list[str] = []
    changed = _git_changed_files(workspace)
    for changed_file in changed:
        if not any(changed_file.startswith(prefix) for prefix in protected_prefixes):
            continue
        if changed_file not in allowed_touched_files:
            violations.append(changed_file)
    return sorted(set(violations))


def run_task(workspace: str, task_file: str) -> TaskRunResult:
    workspace_path = Path(workspace).resolve()
    spec_path = Path(task_file)
    if not spec_path.is_absolute():
        spec_path = workspace_path / spec_path

    spec: TaskRunSpec | None = None
    action_type_hint = ""

    try:
        spec = load_task_run_spec(str(spec_path))
        action_type_hint = spec.action_type or ""

        config = load_full_config(str(workspace_path / "configs"))
        action_type = spec.action_type or config.runtime.default_action_type
        warnings, blockers = evaluate_avoidance_rules(
            workspace_path,
            action_type=action_type,
            llm_api_key_env=config.runtime.llm_api_key_env,
        )
        for item in warnings:
            logger.warning("known issue warning task_id=%s: %s", spec.id, item)
        if blockers:
            raise ValueError("blocked by persisted avoidance rules:\n" + "\n".join(f"- {x}" for x in blockers))

        enforce_strict_codegen(config, spec)

        if config.runtime.strict_industrial_mode:
            if not _is_git_repo(workspace_path):
                raise ValueError("strict_industrial_mode requires workspace to be a git repository")
            protected_prefixes = [str(x).replace("\\", "/") for x in config.policy_rules.require_api_patch_for_paths]
            if config.policy_rules.forbid_manual_business_edits and protected_prefixes:
                known_api_touched = _collect_all_touched_files(workspace_path)
                violations = _manual_edit_violations(workspace_path, protected_prefixes, known_api_touched)
                if violations:
                    raise ValueError(
                        "manual edit detected before run outside API patch ledger:\n"
                        + "\n".join(f"- {item}" for item in violations)
                    )

        logger.info(
            "task run started task_id=%s action_type=%s strict_codegen=%s strict_industrial=%s workspace=%s",
            spec.id,
            action_type,
            config.runtime.strict_codegen_mode,
            config.runtime.strict_industrial_mode,
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
        outcome.state.metadata["strict_industrial_mode"] = config.runtime.strict_industrial_mode

        if config.runtime.strict_codegen_mode and outcome.status.value == "COMPLETED":
            protocol = _apply_generated_patches(workspace_path, config, spec, outcome)
            outcome.state.metadata["patch_ledger"] = protocol["ledger_path"]
            outcome.state.metadata["patch_request_id"] = protocol["request_id"]
            outcome.state.metadata["patch_touched_files"] = protocol["touched_files"]

        error_events = _collect_outcome_error_events(outcome)
        error_report_path = ""
        if error_events:
            error_report = build_report(task_id=spec.id, events=error_events)
            error_report_path = str(write_error_report(workspace_path, error_report))
            logger.warning("task run captured %d error event(s), report=%s", len(error_events), error_report_path)

        state_path = _write_state(workspace_path, outcome)
        docs = _update_docs(workspace_path, task, outcome)
        run_report = _write_run_report(workspace_path, spec, outcome, docs, context_report, error_report_path)

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
            error_report_path=error_report_path,
        )
    except Exception as exc:
        fallback_task_id = spec.id if spec is not None else spec_path.stem or "unknown-task"
        report_path = _persist_exception_report(workspace_path, fallback_task_id, exc, action_type_hint)
        logger.exception("task run failed task_id=%s error_report=%s", fallback_task_id, report_path)
        raise ValueError(f"{exc}\nerror report: {report_path}") from exc


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

    config = load_full_config(str(base / "configs"))
    if config.runtime.strict_codegen_mode:
        ledger_path = base / ".agentkit" / "patches" / f"{task_id}.json"
        if not ledger_path.exists():
            missing.append(str(ledger_path))

        protected_prefixes = [str(x).replace("\\", "/") for x in config.policy_rules.require_api_patch_for_paths]
        if config.policy_rules.forbid_manual_business_edits and protected_prefixes:
            if config.runtime.strict_industrial_mode and not _is_git_repo(base):
                missing.append("strict_industrial_mode requires workspace to be a git repository")
            else:
                if config.runtime.strict_industrial_mode:
                    allowed_touched = _collect_all_touched_files(base)
                else:
                    payload = _read_task_ledger(ledger_path)
                    allowed_touched = {str(x).replace("\\", "/") for x in payload.get("touched_files", [])}
                violations = _manual_edit_violations(base, protected_prefixes, allowed_touched)
                for changed_file in violations:
                    missing.append(f"manual edit detected outside API patch ledger: {changed_file}")

    return (len(missing) == 0, missing)

