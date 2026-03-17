from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentkit.runner.api import run_task, verify_task_run
from agentkit.runner.env_check import ensure_workspace_environment, inspect_environment
from agentkit.runner.error_feedback import adopt_rules_from_report, load_latest_error_report
from agentkit.runner.serve_cli import run_server
from agentkit.starter.apply import apply_starter_project
from agentkit.starter.clean import clean_project
from agentkit.starter.init import initialize_starter_project
from agentkit.starter.migrate import migrate_existing_project
from agentkit.starter.profiles import PROFILES


def _parse_indexes(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        item = token.strip()
        if not item:
            continue
        values.append(int(item))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a new project")
    p_init.add_argument("--target", required=True)
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--profile", choices=sorted(PROFILES.keys()), default="minimal")
    p_init.add_argument("--force", action="store_true")

    p_apply = sub.add_parser("apply", help="Initialize and apply customization")
    p_apply.add_argument("--target", required=True)
    p_apply.add_argument("--name", required=True)
    p_apply.add_argument("--profile", choices=sorted(PROFILES.keys()), default="minimal")
    p_apply.add_argument("--config")
    p_apply.add_argument("--force", action="store_true")

    p_migrate = sub.add_parser("migrate", help="Migrate existing project safely")
    p_migrate.add_argument("--target", default=".")
    p_migrate.add_argument("--name")
    p_migrate.add_argument("--profile", choices=sorted(PROFILES.keys()), default="minimal")
    p_migrate.add_argument("--no-sidecars", action="store_true")

    p_clean = sub.add_parser("clean", help="Clean AgentKit generated artifacts")
    p_clean.add_argument("--target", default=".")
    p_clean.add_argument("--scope", choices=["runtime", "docs", "migration", "all"], default="runtime")
    p_clean.add_argument("--dry-run", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Diagnose AgentKit environment binding")
    p_doctor.add_argument("--workspace", default=".")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.add_argument("--strict", action="store_true")

    p_run = sub.add_parser("run", help="Run a task through AgentKit pipeline")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--workspace", default=".")

    p_verify = sub.add_parser("verify", help="Verify required run artifacts")
    p_verify.add_argument("--task-id", required=True)
    p_verify.add_argument("--workspace", default=".")

    p_errors = sub.add_parser("errors", help="List task errors and optionally persist selected ones as avoidance rules")
    p_errors.add_argument("--task-id", required=True)
    p_errors.add_argument("--workspace", default=".")
    p_errors.add_argument("--save", help="Comma-separated indexes to persist, e.g. 1,3")
    p_errors.add_argument("--mode", choices=["warn", "block"], default="warn")
    p_errors.add_argument("--note", default="")
    p_errors.add_argument("--interactive", action="store_true")

    p_serve = sub.add_parser("serve", help="Serve AgentKit run/verify HTTP API")
    p_serve.add_argument("--workspace", default=".")
    p_serve.add_argument("--host")
    p_serve.add_argument("--port", type=int)
    p_serve.add_argument("--token")
    p_serve.add_argument("--require-token", action="store_true")
    p_serve.add_argument("--log-level")
    p_serve.add_argument("--log-file")
    p_serve.add_argument("--no-log-file", action="store_true")
    p_serve.add_argument("--no-config", action="store_true")

    args = parser.parse_args()

    if args.command == "init":
        result = initialize_starter_project(Path(args.target), args.name, profile_name=args.profile, force=args.force)
        print(result)
    elif args.command == "apply":
        result = apply_starter_project(
            target_dir=Path(args.target),
            project_name=args.name,
            profile_name=args.profile,
            spec_path=Path(args.config) if args.config else None,
            force=args.force,
        )
        print(result)
    elif args.command == "migrate":
        target = Path(args.target)
        name = args.name or target.name
        result = migrate_existing_project(
            target_dir=target,
            project_name=name,
            profile_name=args.profile,
            create_sidecars=not args.no_sidecars,
        )
        print(result)
    elif args.command == "clean":
        result = clean_project(target_dir=Path(args.target), scope=args.scope, dry_run=args.dry_run)
        print(result)
    elif args.command == "doctor":
        report = inspect_environment(args.workspace)
        if args.json:
            print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
        else:
            print(report)
        if args.strict and not report.is_valid:
            raise SystemExit(1)
    elif args.command == "run":
        ensure_workspace_environment(args.workspace)
        result = run_task(workspace=args.workspace, task_file=args.task)
        print(result)
    elif args.command == "verify":
        ensure_workspace_environment(args.workspace)
        ok, missing = verify_task_run(workspace=args.workspace, task_id=args.task_id)
        if not ok:
            for item in missing:
                print(item)
            raise SystemExit(1)
        print("Verification passed")
    elif args.command == "errors":
        workspace = Path(args.workspace).resolve()
        report = load_latest_error_report(workspace, args.task_id)
        if report is None:
            print(f"No error report found for task_id={args.task_id}")
            raise SystemExit(1)

        print(f"Task: {report.task_id}")
        print(f"Report: {report.report_id}")
        print(f"Created: {report.created_at}")
        for idx, event in enumerate(report.events, start=1):
            print(f"[{idx}] code={event.code} stage={event.stage} action={event.action_type or '-'}")
            print(f"    message: {event.message}")
            print(f"    suggestion: {event.suggestion}")
            print(f"    fingerprint: {event.fingerprint}")

        selection_raw = args.save or ""
        if args.interactive and not selection_raw:
            selection_raw = input("Select indexes to persist (e.g. 1,3), empty to skip: ").strip()

        if selection_raw:
            selected = _parse_indexes(selection_raw)
            added, path = adopt_rules_from_report(
                workspace,
                report,
                selected,
                mode=args.mode,
                note=args.note,
            )
            print(f"Persisted {added} rule(s) to {path}")
    elif args.command == "serve":
        run_server(
            workspace=args.workspace,
            host=args.host,
            port=args.port,
            token=args.token,
            require_token=args.require_token,
            log_level=args.log_level,
            log_file=args.log_file,
            no_log_file=args.no_log_file,
            no_config=args.no_config,
        )


if __name__ == "__main__":
    main()
