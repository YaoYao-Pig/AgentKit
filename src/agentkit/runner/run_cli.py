from __future__ import annotations

from argparse import ArgumentParser

from .api import run_task


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run a task through AgentKit runtime pipeline")
    parser.add_argument("--task", required=True, help="Task YAML file path")
    parser.add_argument("--workspace", default=".", help="Project workspace root")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = run_task(workspace=args.workspace, task_file=args.task)
    print(f"Task: {result.task_id}")
    print(f"Status: {result.status}")
    print(f"State: {result.state_path}")
    print(f"Context: {result.context_report_path}")
    print(f"Run report: {result.run_report_path}")
    print("Generated docs:")
    for path in result.generated_docs:
        print(f"- {path}")


if __name__ == "__main__":
    main()
