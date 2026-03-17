from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib
import shutil
import sys


@dataclass(slots=True)
class EnvironmentReport:
    workspace: str
    python_executable: str
    command_path: str
    module_path: str
    workspace_source_path: str
    workspace_has_local_source: bool
    module_under_workspace_source: bool
    is_valid: bool
    issues: list[str]


def inspect_environment(workspace: str) -> EnvironmentReport:
    workspace_path = Path(workspace).resolve()
    source_path = workspace_path / "src" / "agentkit"

    module = importlib.import_module("agentkit")
    module_file = Path(getattr(module, "__file__", "")).resolve()

    command_path = shutil.which("agentkit-serve") or ""

    has_local_source = source_path.exists()
    module_under_source = source_path in module_file.parents if has_local_source else False

    issues: list[str] = []
    if has_local_source and not module_under_source:
        issues.append(
            "resolved agentkit module is not from workspace/src/agentkit; this often means a global package shadowed local code"
        )

    return EnvironmentReport(
        workspace=str(workspace_path),
        python_executable=sys.executable,
        command_path=command_path,
        module_path=str(module_file),
        workspace_source_path=str(source_path),
        workspace_has_local_source=has_local_source,
        module_under_workspace_source=module_under_source,
        is_valid=len(issues) == 0,
        issues=issues,
    )


def ensure_workspace_environment(workspace: str) -> EnvironmentReport:
    report = inspect_environment(workspace)
    if not report.is_valid:
        details = "\n".join(f"- {item}" for item in report.issues)
        raise ValueError(
            "environment check failed:\n"
            f"workspace: {report.workspace}\n"
            f"python: {report.python_executable}\n"
            f"agentkit module: {report.module_path}\n"
            f"expected source: {report.workspace_source_path}\n"
            f"agentkit-serve command: {report.command_path or '(not found)'}\n"
            f"issues:\n{details}\n"
            "run `agentkit-doctor --workspace <path>` for diagnostics"
        )
    return report
