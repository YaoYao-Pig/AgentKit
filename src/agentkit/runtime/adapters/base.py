from __future__ import annotations

import importlib
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from agentkit.config.models import SkillConfig

from ..models import Action, ActionResult, EvidenceRef, PipelineState, Summary


class ToolAdapter(ABC):
    name: str

    @abstractmethod
    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        raise NotImplementedError


@dataclass(slots=True)
class MockAdapter(ToolAdapter):
    name: str = "mock"

    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        return ActionResult(
            action_id=action.id,
            status="success",
            summary=Summary(step_id=action.id, content=f"Mock adapter executed '{action.action_type}'."),
            evidence=[EvidenceRef(path="adapter://mock", note=skill.purpose)],
            output={"adapter": self.name, "params": action.params},
        )


@dataclass(slots=True)
class ShellCommandAdapter(ToolAdapter):
    name: str = "shell"

    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        command_template = action.params.get("command") or skill.command
        if not command_template:
            raise ValueError(f"skill '{action.action_type}' requires command template")

        merged_params = {**skill.static_params, **action.params}
        command = str(command_template).format(**merged_params)

        completed = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        status = "success" if completed.returncode == 0 else "failed"

        return ActionResult(
            action_id=action.id,
            status=status,
            summary=Summary(
                step_id=action.id,
                content=f"Shell command executed with exit code {completed.returncode}.",
            ),
            evidence=[EvidenceRef(path="adapter://shell", note=command)],
            output={
                "adapter": self.name,
                "command": command,
                "returncode": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        )


@dataclass(slots=True)
class PythonCallableAdapter(ToolAdapter):
    name: str = "python_callable"

    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        if not skill.module or not skill.function:
            raise ValueError(f"skill '{action.action_type}' requires module and function")

        merged_params = {**skill.static_params, **action.params}
        module = importlib.import_module(skill.module)
        fn = getattr(module, skill.function)
        result = fn(merged_params, state)

        output = result if isinstance(result, dict) else {"result": result}
        status = str(output.get("status", "success"))

        return ActionResult(
            action_id=action.id,
            status=status,
            summary=Summary(step_id=action.id, content=f"Python callable '{skill.module}.{skill.function}' executed."),
            evidence=[EvidenceRef(path="adapter://python_callable", note=f"{skill.module}.{skill.function}")],
            output={"adapter": self.name, **output},
        )


def default_adapter_registry() -> dict[str, ToolAdapter]:
    return {
        "mock": MockAdapter(),
        "shell": ShellCommandAdapter(),
        "python_callable": PythonCallableAdapter(),
    }
