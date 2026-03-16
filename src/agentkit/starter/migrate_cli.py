from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from .migrate import migrate_existing_project
from .profiles import PROFILES


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Safely migrate an existing project to AgentKit starter structure")
    parser.add_argument("--target", default=".", help="Existing project directory")
    parser.add_argument("--name", help="Project name (defaults to target directory name)")
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), default="minimal")
    parser.add_argument(
        "--no-sidecars",
        action="store_true",
        help="Do not generate *.starter.* sidecar files for existing key files",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    target = Path(args.target)

    result = migrate_existing_project(
        target_dir=target,
        project_name=args.name or target.resolve().name,
        profile_name=args.profile,
        create_sidecars=not args.no_sidecars,
    )

    print(f"Migrated project: {result.project_name}")
    print(f"Profile: {result.profile}")
    print(f"Root: {result.target_dir}")
    print(f"Migration report: {result.report_path}")
    print("Created/updated paths:")
    for path in result.generated_paths:
        print(f"- {path}")
    if result.sidecar_paths:
        print("Sidecar files:")
        for path in result.sidecar_paths:
            print(f"- {path}")


if __name__ == "__main__":
    main()
