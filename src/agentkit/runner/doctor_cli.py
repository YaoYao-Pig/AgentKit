from __future__ import annotations

from argparse import ArgumentParser
import json

from .env_check import inspect_environment


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Diagnose AgentKit runtime environment and path resolution")
    parser.add_argument("--workspace", default=".", help="Project workspace root")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when environment is invalid")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    report = inspect_environment(args.workspace)

    if args.json:
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
    else:
        print(f"Workspace: {report.workspace}")
        print(f"Python: {report.python_executable}")
        print(f"agentkit module: {report.module_path}")
        print(f"Expected source: {report.workspace_source_path}")
        print(f"agentkit-serve command: {report.command_path or '(not found)'}")
        print(f"Workspace has local source: {report.workspace_has_local_source}")
        print(f"Module under workspace source: {report.module_under_workspace_source}")
        print(f"Valid: {report.is_valid}")
        if report.issues:
            print("Issues:")
            for item in report.issues:
                print(f"- {item}")

    if args.strict and not report.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
