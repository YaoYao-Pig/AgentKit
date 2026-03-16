from __future__ import annotations

from argparse import ArgumentParser

from .api import verify_task_run


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Verify required artifacts for an AgentKit task run")
    parser.add_argument("--task-id", required=True, help="Task id to verify")
    parser.add_argument("--workspace", default=".", help="Project workspace root")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ok, missing = verify_task_run(workspace=args.workspace, task_id=args.task_id)
    if ok:
        print("Verification passed")
        return

    print("Verification failed. Missing artifacts:")
    for item in missing:
        print(f"- {item}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
