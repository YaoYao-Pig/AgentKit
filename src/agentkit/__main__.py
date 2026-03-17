from __future__ import annotations

import argparse
from pathlib import Path

from agentkit.runner.api import run_task, verify_task_run
from agentkit.runner.serve_cli import run_server
from agentkit.starter.apply import apply_starter_project
from agentkit.starter.clean import clean_project
from agentkit.starter.init import initialize_starter_project
from agentkit.starter.migrate import migrate_existing_project
from agentkit.starter.profiles import PROFILES


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

    p_run = sub.add_parser("run", help="Run a task through AgentKit pipeline")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--workspace", default=".")

    p_verify = sub.add_parser("verify", help="Verify required run artifacts")
    p_verify.add_argument("--task-id", required=True)
    p_verify.add_argument("--workspace", default=".")

    p_serve = sub.add_parser("serve", help="Serve AgentKit run/verify HTTP API")
    p_serve.add_argument("--workspace", default=".")
    p_serve.add_argument("--host")
    p_serve.add_argument("--port", type=int)
    p_serve.add_argument("--token")
    p_serve.add_argument("--require-token", action="store_true")
    p_serve.add_argument("--log-level")
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
    elif args.command == "run":
        result = run_task(workspace=args.workspace, task_file=args.task)
        print(result)
    elif args.command == "verify":
        ok, missing = verify_task_run(workspace=args.workspace, task_id=args.task_id)
        if not ok:
            for item in missing:
                print(item)
            raise SystemExit(1)
        print("Verification passed")
    elif args.command == "serve":
        run_server(
            workspace=args.workspace,
            host=args.host,
            port=args.port,
            token=args.token,
            require_token=args.require_token,
            log_level=args.log_level,
            no_config=args.no_config,
        )


if __name__ == "__main__":
    main()



