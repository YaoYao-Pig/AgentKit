from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree


@dataclass(slots=True)
class CleanResult:
    target_dir: str
    scope: str
    dry_run: bool
    removed_paths: list[str]
    missing_paths: list[str]


def _remove_path(path: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    if path.is_dir():
        rmtree(path)
    else:
        path.unlink()
    return True


def _collect_scope_paths(target_dir: Path, scope: str) -> list[Path]:
    paths: list[Path] = []

    if scope in {"runtime", "all"}:
        paths.append(target_dir / ".agentkit")

    if scope in {"docs", "all"}:
        generated = target_dir / "docs" / "generated"
        if generated.exists():
            for path in generated.rglob("*"):
                if path.is_file() and path.name != ".gitkeep":
                    paths.append(path)

    if scope in {"migration", "all"}:
        paths.extend(target_dir.glob("*.starter.*"))
        configs = target_dir / "configs"
        if configs.exists():
            paths.extend(configs.glob("*.starter.*"))
        templates = target_dir / "docs" / "templates"
        if templates.exists():
            paths.extend(templates.glob("*.starter.*"))
        report = target_dir / "docs" / "MIGRATION_REPORT.md"
        paths.append(report)

    unique = sorted({p.resolve() for p in paths}, key=lambda p: str(p))
    return list(unique)


def clean_project(target_dir: Path, scope: str = "runtime", dry_run: bool = False) -> CleanResult:
    valid = {"runtime", "docs", "migration", "all"}
    if scope not in valid:
        raise ValueError(f"invalid scope '{scope}', expected one of: {sorted(valid)}")

    target = target_dir.resolve()
    removed: list[str] = []
    missing: list[str] = []

    for path in _collect_scope_paths(target, scope):
        if not path.exists():
            missing.append(str(path))
            continue
        _remove_path(path, dry_run=dry_run)
        removed.append(str(path))

    return CleanResult(
        target_dir=str(target),
        scope=scope,
        dry_run=dry_run,
        removed_paths=removed,
        missing_paths=missing,
    )
