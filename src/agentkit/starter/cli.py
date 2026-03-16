from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from .init import initialize_starter_project
from .profiles import PROFILES


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Initialize a new pipeline project from AgentKit starter")
    parser.add_argument("--target", required=True, help="Target directory for generated project")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), default="minimal")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files when needed")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = initialize_starter_project(
        target_dir=Path(args.target),
        project_name=args.name,
        profile_name=args.profile,
        force=args.force,
    )

    print(f"Initialized starter project: {result.project_name}")
    print(f"Profile: {result.profile}")
    print(f"Root: {result.target_dir}")
    print("Generated paths:")
    for path in result.generated_paths:
        print(f"- {path}")


if __name__ == "__main__":
    main()
