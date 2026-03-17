from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from .clean import clean_project


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Clean AgentKit-generated artifacts from a project")
    parser.add_argument("--target", default=".", help="Project root directory")
    parser.add_argument(
        "--scope",
        choices=["runtime", "docs", "migration", "all"],
        default="runtime",
        help="Cleanup scope",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview cleanup targets without deleting")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = clean_project(target_dir=Path(args.target), scope=args.scope, dry_run=args.dry_run)
    print(f"Target: {result.target_dir}")
    print(f"Scope: {result.scope}")
    print(f"Dry run: {result.dry_run}")
    print("Affected paths:")
    for path in result.removed_paths:
        print(f"- {path}")
    if not result.removed_paths:
        print("- none")


if __name__ == "__main__":
    main()
