from __future__ import annotations

import argparse
from pathlib import Path

from .error_feedback import adopt_rules_from_report, load_latest_error_report


def _parse_indexes(raw: str) -> list[int]:
    values: list[int] = []
    for token in raw.split(","):
        item = token.strip()
        if item:
            values.append(int(item))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentkit-errors", description="Inspect and persist AgentKit error feedback rules")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--save", help="Comma-separated indexes to persist, e.g. 1,3")
    parser.add_argument("--mode", choices=["warn", "block"], default="warn")
    parser.add_argument("--note", default="")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

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

    if not selection_raw:
        return

    selected = _parse_indexes(selection_raw)
    added, path = adopt_rules_from_report(
        workspace,
        report,
        selected,
        mode=args.mode,
        note=args.note,
    )
    print(f"Persisted {added} rule(s) to {path}")


if __name__ == "__main__":
    main()
