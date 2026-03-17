from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ErrorEvent:
    code: str
    stage: str
    message: str
    action_type: str = ""
    fingerprint: str = ""
    suggestion: str = ""


@dataclass(slots=True)
class ErrorReport:
    report_id: str
    task_id: str
    created_at: str
    events: list[ErrorEvent] = field(default_factory=list)


@dataclass(slots=True)
class AvoidanceRule:
    fingerprint: str
    code: str
    mode: str
    note: str
    action_type: str = ""
    created_at: str = field(default_factory=_utc_now_iso)


def classify_error_code(message: str) -> str:
    text = message.lower()
    if "createprocesswithlogonw failed: 1326" in text:
        return "windows_logon_1326"
    if "strict_codegen_mode requires environment variable" in text or "agentkit_llm_api_key" in text:
        return "missing_env_api_key"
    if "unauthorized" in text:
        return "api_unauthorized"
    if "strict_codegen_mode requires llm response.patches" in text:
        return "invalid_codegen_payload"
    if "path not allowed by module rules" in text:
        return "module_rules_blocked_path"
    return "runtime_error"


def suggestion_for_code(code: str) -> str:
    mapping = {
        "windows_logon_1326": "Use approved escalated command prefixes and avoid unmanaged process launch/kill flows.",
        "missing_env_api_key": "Set AGENTKIT_LLM_API_KEY (or configured llm_api_key_env) before running in strict mode.",
        "api_unauthorized": "Pass Authorization: Bearer <token> or X-AgentKit-Token header that matches runtime config.",
        "invalid_codegen_payload": "Ensure llm_codegen returns JSON object with request_id and non-empty patches list.",
        "module_rules_blocked_path": "Adjust module_rules.allowed_paths or patch target path to stay inside allowed scope.",
        "runtime_error": "Inspect .agentkit/logs and task run report, then add a targeted preventive rule if this recurs.",
    }
    return mapping.get(code, mapping["runtime_error"])


def _fingerprint(code: str, stage: str, message: str, action_type: str) -> str:
    norm = re.sub(r"\s+", " ", message.strip().lower())
    digest = hashlib.sha256(f"{code}|{stage}|{action_type}|{norm}".encode("utf-8")).hexdigest()
    return digest[:16]


def make_event(message: str, *, stage: str, action_type: str = "") -> ErrorEvent:
    code = classify_error_code(message)
    fp = _fingerprint(code, stage, message, action_type)
    return ErrorEvent(
        code=code,
        stage=stage,
        message=message.strip(),
        action_type=action_type,
        fingerprint=fp,
        suggestion=suggestion_for_code(code),
    )


def build_report(task_id: str, events: list[ErrorEvent]) -> ErrorReport:
    report_id = hashlib.sha256(f"{task_id}|{_utc_now_iso()}".encode("utf-8")).hexdigest()[:12]
    return ErrorReport(report_id=report_id, task_id=task_id, created_at=_utc_now_iso(), events=events)


def write_error_report(workspace: Path, report: ErrorReport) -> Path:
    out_dir = workspace / ".agentkit" / "errors"
    out_dir.mkdir(parents=True, exist_ok=True)
    named = out_dir / f"{report.task_id}--{report.report_id}.json"
    latest = out_dir / f"{report.task_id}.latest.json"
    payload = {
        "report_id": report.report_id,
        "task_id": report.task_id,
        "created_at": report.created_at,
        "events": [asdict(x) for x in report.events],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    named.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return named


def load_latest_error_report(workspace: Path, task_id: str) -> ErrorReport | None:
    latest = workspace / ".agentkit" / "errors" / f"{task_id}.latest.json"
    if not latest.exists():
        return None
    payload = json.loads(latest.read_text(encoding="utf-8"))
    events: list[ErrorEvent] = []
    for raw in payload.get("events", []):
        if not isinstance(raw, dict):
            continue
        events.append(
            ErrorEvent(
                code=str(raw.get("code") or "runtime_error"),
                stage=str(raw.get("stage") or "unknown"),
                message=str(raw.get("message") or ""),
                action_type=str(raw.get("action_type") or ""),
                fingerprint=str(raw.get("fingerprint") or ""),
                suggestion=str(raw.get("suggestion") or ""),
            )
        )
    return ErrorReport(
        report_id=str(payload.get("report_id") or ""),
        task_id=str(payload.get("task_id") or task_id),
        created_at=str(payload.get("created_at") or ""),
        events=events,
    )


def _rules_path(workspace: Path) -> Path:
    return workspace / ".agentkit" / "feedback" / "avoidance_rules.json"


def load_avoidance_rules(workspace: Path) -> list[AvoidanceRule]:
    path = _rules_path(workspace)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules: list[AvoidanceRule] = []
    for raw in payload.get("rules", []):
        if not isinstance(raw, dict):
            continue
        rules.append(
            AvoidanceRule(
                fingerprint=str(raw.get("fingerprint") or ""),
                code=str(raw.get("code") or "runtime_error"),
                mode=str(raw.get("mode") or "warn"),
                note=str(raw.get("note") or ""),
                action_type=str(raw.get("action_type") or ""),
                created_at=str(raw.get("created_at") or _utc_now_iso()),
            )
        )
    return rules


def save_avoidance_rules(workspace: Path, rules: list[AvoidanceRule]) -> Path:
    path = _rules_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"rules": [asdict(rule) for rule in rules]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def adopt_rules_from_report(
    workspace: Path,
    report: ErrorReport,
    selected_indexes: list[int],
    *,
    mode: str = "warn",
    note: str = "",
) -> tuple[int, Path]:
    existing = load_avoidance_rules(workspace)
    by_key = {(x.fingerprint, x.mode): x for x in existing}
    added = 0

    for index in selected_indexes:
        zero = index - 1
        if zero < 0 or zero >= len(report.events):
            continue
        event = report.events[zero]
        key = (event.fingerprint, mode)
        if key in by_key:
            continue
        rule_note = note.strip() or f"Adopted from task {report.task_id} error #{index}"
        rule = AvoidanceRule(
            fingerprint=event.fingerprint,
            code=event.code,
            mode=mode,
            note=rule_note,
            action_type=event.action_type,
        )
        existing.append(rule)
        by_key[key] = rule
        added += 1

    saved = save_avoidance_rules(workspace, existing)
    return added, saved


def evaluate_avoidance_rules(
    workspace: Path,
    *,
    action_type: str,
    llm_api_key_env: str,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    for rule in load_avoidance_rules(workspace):
        if rule.action_type and rule.action_type != action_type:
            continue

        matched = False
        if rule.code == "missing_env_api_key":
            matched = not bool(os.getenv(llm_api_key_env, "").strip())
        elif rule.code in {"windows_logon_1326", "api_unauthorized"}:
            matched = True

        if not matched:
            continue

        message = f"[{rule.code}] {rule.note}".strip()
        if rule.mode == "block":
            blockers.append(message)
        else:
            warnings.append(message)

    return warnings, blockers
