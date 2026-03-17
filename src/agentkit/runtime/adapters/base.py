from __future__ import annotations

import importlib
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request

from agentkit.config.models import SkillConfig

from ..models import Action, ActionResult, EvidenceRef, PipelineState, Summary


logger = logging.getLogger("agentkit.adapter")


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


@dataclass(slots=True)
class LlmHttpAdapter(ToolAdapter):
    name: str = "llm_http"

    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        endpoint = str(action.params.get("endpoint") or skill.static_params.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError(f"skill '{action.action_type}' requires endpoint")

        prompt = str(action.params.get("prompt") or skill.static_params.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"skill '{action.action_type}' requires prompt")

        model = str(action.params.get("model") or skill.static_params.get("model") or "generic").strip()
        api_key_env = str(action.params.get("api_key_env") or skill.static_params.get("api_key_env") or "").strip()
        api_key = str(action.params.get("api_key") or "").strip()
        if not api_key and api_key_env:
            api_key = os.getenv(api_key_env, "").strip()

        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "context": {
                "task_id": state.task_id,
                "phase": state.current_phase,
                "retries": state.retries,
                "metadata": action.params.get("context", {}),
            },
        }
        extra_payload = action.params.get("request_payload")
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        logger.info(
            "llm_http request action_id=%s task_id=%s endpoint=%s model=%s prompt_chars=%d",
            action.id,
            state.task_id,
            endpoint,
            model,
            len(prompt),
        )

        with request.urlopen(req, timeout=60) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}

        if not isinstance(parsed, dict):
            raise ValueError("llm response must be a JSON object")

        status = str(parsed.get("status", "success"))
        summary_text = str(parsed.get("summary") or f"LLM endpoint returned status '{status}'.")

        logger.info(
            "llm_http response action_id=%s task_id=%s http_status=%s llm_status=%s",
            action.id,
            state.task_id,
            status_code,
            status,
        )

        return ActionResult(
            action_id=action.id,
            status=status,
            summary=Summary(step_id=action.id, content=summary_text),
            evidence=[EvidenceRef(path=f"adapter://llm_http", note=endpoint)],
            output={"adapter": self.name, "endpoint": endpoint, "response": parsed},
        )


@dataclass(slots=True)
class FilePatchAdapter(ToolAdapter):
    workspace_root: str | None = None
    allowed_paths: list[str] | None = None
    name: str = "file_patch"

    def _normalize_allowed(self, state: PipelineState) -> list[str]:
        sources = []
        if self.allowed_paths:
            sources.extend(self.allowed_paths)
        metadata_allowed = state.metadata.get("module_rules", {}).get("allowed_paths", [])
        if isinstance(metadata_allowed, list):
            sources.extend(str(item) for item in metadata_allowed)
        normalized: list[str] = []
        for raw in sources:
            prefix = str(raw).replace("\\", "/").lstrip("./")
            if not prefix:
                continue
            if not prefix.endswith("/"):
                prefix += "/"
            normalized.append(prefix)
        return sorted(set(normalized))

    def _is_path_allowed(self, rel_path: str, allowed: list[str]) -> bool:
        if not allowed:
            return True
        normalized = rel_path.replace("\\", "/")
        return any(normalized.startswith(prefix) for prefix in allowed)

    def execute(self, action: Action, state: PipelineState, skill: SkillConfig) -> ActionResult:
        workspace = Path(self.workspace_root or state.metadata.get("workspace_root") or ".").resolve()
        patches = action.params.get("patches") or skill.static_params.get("patches")
        if not isinstance(patches, list) or not patches:
            raise ValueError(f"skill '{action.action_type}' requires non-empty patches list")

        allowed = self._normalize_allowed(state)
        written: list[str] = []

        for index, item in enumerate(patches):
            if not isinstance(item, dict):
                raise ValueError(f"patch at index {index} must be an object")

            raw_path = str(item.get("path") or "").strip()
            if not raw_path:
                raise ValueError(f"patch at index {index} missing path")

            rel_path = Path(raw_path)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise ValueError(f"unsafe patch path: {raw_path}")

            rel_norm = rel_path.as_posix().lstrip("./")
            if not self._is_path_allowed(rel_norm, allowed):
                raise ValueError(f"path not allowed by module rules: {rel_norm}")

            mode = str(item.get("mode") or "overwrite").strip().lower()
            content = str(item.get("content") or "")
            target = (workspace / rel_path).resolve()
            if workspace not in target.parents and target != workspace:
                raise ValueError(f"patch target escapes workspace: {raw_path}")

            target.parent.mkdir(parents=True, exist_ok=True)
            if mode == "overwrite":
                target.write_text(content, encoding="utf-8")
            elif mode == "append":
                with target.open("a", encoding="utf-8") as fh:
                    fh.write(content)
            else:
                raise ValueError(f"unsupported patch mode: {mode}")

            written.append(str(target))

        return ActionResult(
            action_id=action.id,
            status="success",
            summary=Summary(step_id=action.id, content=f"Applied {len(written)} patch(es)."),
            evidence=[EvidenceRef(path="adapter://file_patch", note="write operations completed")],
            output={"adapter": self.name, "written": written},
        )


def default_adapter_registry(
    workspace_root: str | None = None,
    allowed_paths: list[str] | None = None,
) -> dict[str, ToolAdapter]:
    return {
        "mock": MockAdapter(),
        "shell": ShellCommandAdapter(),
        "python_callable": PythonCallableAdapter(),
        "llm_http": LlmHttpAdapter(),
        "file_patch": FilePatchAdapter(workspace_root=workspace_root, allowed_paths=allowed_paths),
    }


