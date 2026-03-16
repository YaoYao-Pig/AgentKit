from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2

from .init import (
    ROOT_AGENTS_TEMPLATE,
    ROOT_README_TEMPLATE,
    InitResult,
    _repo_root,
    initialize_starter_project,
)


@dataclass(slots=True)
class MigrateResult(InitResult):
    report_path: str
    sidecar_paths: list[str]


def _sidecar_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.starter{path.suffix}")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_to_sidecar(src: Path, dst_existing: Path) -> Path:
    sidecar = _sidecar_path(dst_existing)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    copy2(src, sidecar)
    return sidecar


def migrate_existing_project(
    target_dir: Path,
    project_name: str,
    profile_name: str = "minimal",
    create_sidecars: bool = True,
) -> MigrateResult:
    target_dir = target_dir.resolve()
    root = _repo_root()

    existing_before: set[Path] = {p.resolve() for p in target_dir.rglob("*") if p.is_file()} if target_dir.exists() else set()

    init_result = initialize_starter_project(
        target_dir=target_dir,
        project_name=project_name,
        profile_name=profile_name,
        force=False,
        generate_default_docs=False,
    )

    sidecars: list[Path] = []
    preserved: list[Path] = []

    key_text_files = [
        target_dir / "README.md",
        target_dir / "AGENTS.md",
    ]

    if create_sidecars:
        readme = target_dir / "README.md"
        if readme.resolve() in existing_before:
            sidecar = target_dir / "README.starter.md"
            _write_text(sidecar, ROOT_README_TEMPLATE.format(project_name=project_name))
            sidecars.append(sidecar)
            preserved.append(readme)

        agents = target_dir / "AGENTS.md"
        if agents.resolve() in existing_before:
            sidecar = target_dir / "AGENTS.starter.md"
            _write_text(sidecar, ROOT_AGENTS_TEMPLATE)
            sidecars.append(sidecar)
            preserved.append(agents)

        config_files = [
            "system_profile.yaml",
            "skills_index.yaml",
            "policy_rules.yaml",
            "module_rules.yaml",
            "runtime.yaml",
        ]
        for name in config_files:
            dst = target_dir / "configs" / name
            if dst.resolve() in existing_before:
                src = root / "configs" / name
                sidecars.append(_copy_to_sidecar(src, dst))
                preserved.append(dst)

        template_files = [
            "project_charter.md",
            "task_model.md",
            "decision_log.md",
            "risk_register.md",
            "milestone_report.md",
            "handoff_note.md",
        ]
        for name in template_files:
            dst = target_dir / "docs" / "templates" / name
            if dst.resolve() in existing_before:
                src = root / "docs" / "templates" / name
                sidecars.append(_copy_to_sidecar(src, dst))
                preserved.append(dst)

    report = target_dir / "docs" / "MIGRATION_REPORT.md"
    report_lines = [
        "# AgentKit Migration Report",
        "",
        f"- Project: {project_name}",
        f"- Profile: {profile_name}",
        f"- Target: {target_dir}",
        "- Mode: safe migration (non-destructive)",
        "",
        "## Preserved Existing Files",
    ]
    if preserved:
        report_lines.extend([f"- {path.relative_to(target_dir)}" for path in sorted(set(preserved))])
    else:
        report_lines.append("- none")

    report_lines.append("")
    report_lines.append("## Sidecar Files")
    if sidecars:
        report_lines.extend([f"- {path.relative_to(target_dir)}" for path in sorted(set(sidecars))])
    else:
        report_lines.append("- none")

    report_lines.append("")
    report_lines.append("## Next Steps")
    report_lines.append("- Review *.starter.* sidecars and merge needed parts.")
    report_lines.append("- Update configs/module_rules.yaml and configs/skills_index.yaml to match your existing architecture.")
    report_lines.append("- Run python -m pytest and verify docs/generated output.")

    _write_text(report, "\n".join(report_lines) + "\n")

    all_generated = sorted({*init_result.generated_paths, str(report), *[str(path) for path in sidecars]})
    return MigrateResult(
        project_name=init_result.project_name,
        profile=init_result.profile,
        target_dir=init_result.target_dir,
        generated_paths=all_generated,
        report_path=str(report),
        sidecar_paths=sorted(str(path) for path in sidecars),
    )


