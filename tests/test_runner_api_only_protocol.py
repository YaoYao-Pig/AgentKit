import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agentkit.runner.api import run_task, verify_task_run
from agentkit.starter.init import initialize_starter_project


class _WriterStubHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        data = json.loads(body)
        payload = {
            "status": "success",
            "summary": "writer generated patch",
            "request_id": "writer-req-001",
            "patches": [
                {
                    "path": "src/generated/api_only.txt",
                    "mode": "overwrite",
                    "content": f"prompt={data.get('input', '')}",
                }
            ],
        }
        out = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def _write_runtime_yaml(path: Path, endpoint: str, *, strict_industrial: bool = False, strict_auto_init_git: bool = False) -> None:
    path.write_text(
        "\n".join(
            [
                "max_steps: 6",
                "default_action_type: llm_codegen",
                "api_host: 127.0.0.1",
                "api_port: 8787",
                "require_api_token: false",
                "api_token: dev-agentkit-token",
                "api_log_level: INFO",
                "api_log_to_file: true",
                "api_log_file: .agentkit/logs/agentkit-serve.log",
                "strict_codegen_mode: true",
                f"strict_industrial_mode: {'true' if strict_industrial else 'false'}",
                f"strict_industrial_auto_init_git: {'true' if strict_auto_init_git else 'false'}",
                "llm_healthcheck_required: false",
                "llm_endpoint_timeout_sec: 3",
                "llm_api_key_env: AGENTKIT_LLM_API_KEY",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_skills_yaml(path: Path, endpoint: str) -> None:
    path.write_text(
        "\n".join(
            [
                "skills:",
                "  llm_codegen:",
                "    purpose: strict writer",
                "    risk_level: medium",
                "    adapter: llm_http",
                "    static_params:",
                f"      endpoint: \"{endpoint}\"",
                "      model: \"stub\"",
                "      api_key_env: \"AGENTKIT_LLM_API_KEY\"",
                "  apply_generated_patch:",
                "    purpose: apply patch",
                "    risk_level: medium",
                "    adapter: file_patch",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_policy_yaml(path: Path, forbid_manual: bool) -> None:
    path.write_text(
        "\n".join(
            [
                "blocked_action_types: []",
                "review_action_types: []",
                f"forbid_manual_business_edits: {'true' if forbid_manual else 'false'}",
                "require_api_patch_for_paths:",
                "  - src/",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_task_yaml(path: Path) -> None:
    path.write_text(
        """id: api-only-task-001
title: API Only Task
goal: Generate code via API patches only
constraints: []
success_criteria:
  - patch applied
input_sources: []
affected_files:
  - src/generated/api_only.txt
validation_checklist:
  - verify passes
rollback_plan:
  - delete generated file
risk_points:
  - writer returns invalid payload
action:
  type: llm_codegen
  params:
    prompt: generate one file
context:
  module_hints:
    - src/
""",
        encoding="utf-8",
    )


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "agentkit@example.com"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "AgentKit"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=path, check=True, capture_output=True, text=True)


def _setup_workspace(tmp_path: Path, forbid_manual: bool, *, strict_industrial: bool = False, strict_auto_init_git: bool = False) -> tuple[Path, Path]:
    workspace = tmp_path / "project"
    initialize_starter_project(target_dir=workspace, project_name="ApiOnly", profile_name="minimal", force=True)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _WriterStubHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    endpoint = f"http://{host}:{port}/v1/generate"

    _write_runtime_yaml(workspace / "configs" / "runtime.yaml", endpoint, strict_industrial=strict_industrial, strict_auto_init_git=strict_auto_init_git)
    _write_skills_yaml(workspace / "configs" / "skills_index.yaml", endpoint)
    _write_policy_yaml(workspace / "configs" / "policy_rules.yaml", forbid_manual=forbid_manual)
    _write_task_yaml(workspace / "examples" / "task.api_only.yaml")

    return workspace, httpd


def test_strict_api_only_generates_patch_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, httpd = _setup_workspace(tmp_path, forbid_manual=False)
    monkeypatch.setenv("AGENTKIT_LLM_API_KEY", "dummy-key")

    try:
        result = run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))
        assert result.status == "COMPLETED"

        ledger = workspace / ".agentkit" / "patches" / "api-only-task-001.json"
        assert ledger.exists()
        payload = json.loads(ledger.read_text(encoding="utf-8"))
        assert payload["request_id"] == "writer-req-001"
        assert "src/generated/api_only.txt" in payload["touched_files"]

        ok, missing = verify_task_run(workspace=str(workspace), task_id="api-only-task-001")
        assert ok, missing
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_strict_api_only_verify_blocks_manual_business_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, text=True).returncode != 0:
        pytest.skip("git is required for manual edit detection")

    workspace, httpd = _setup_workspace(tmp_path, forbid_manual=True)
    monkeypatch.setenv("AGENTKIT_LLM_API_KEY", "dummy-key")

    try:
        _init_git_repo(workspace)
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))

        manual = workspace / "src" / "manual_hotfix.txt"
        manual.parent.mkdir(parents=True, exist_ok=True)
        manual.write_text("manual edit", encoding="utf-8")

        ok, missing = verify_task_run(workspace=str(workspace), task_id="api-only-task-001")
        assert not ok
        assert any("manual edit detected" in item for item in missing)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_strict_industrial_mode_blocks_manual_edits_before_next_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, text=True).returncode != 0:
        pytest.skip("git is required for strict industrial mode")

    workspace, httpd = _setup_workspace(tmp_path, forbid_manual=True, strict_industrial=True)
    monkeypatch.setenv("AGENTKIT_LLM_API_KEY", "dummy-key")

    try:
        _init_git_repo(workspace)
        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))

        run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))
        ledger = json.loads((workspace / ".agentkit" / "patches" / "api-only-task-001.json").read_text(encoding="utf-8"))
        assert len(ledger.get("rounds", [])) >= 2

        manual = workspace / "src" / "manual_hotfix.txt"
        manual.parent.mkdir(parents=True, exist_ok=True)
        manual.write_text("manual edit", encoding="utf-8")

        with pytest.raises(ValueError) as exc:
            run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))
        assert "manual edit detected before run" in str(exc.value)
    finally:
        httpd.shutdown()
        httpd.server_close()




def test_strict_industrial_mode_auto_inits_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if subprocess.run(["git", "--version"], capture_output=True, text=True).returncode != 0:
        pytest.skip("git is required for strict industrial mode")

    workspace, httpd = _setup_workspace(
        tmp_path,
        forbid_manual=True,
        strict_industrial=True,
        strict_auto_init_git=True,
    )
    monkeypatch.setenv("AGENTKIT_LLM_API_KEY", "dummy-key")

    try:
        result = run_task(workspace=str(workspace), task_file=str(workspace / "examples" / "task.api_only.yaml"))
        assert result.status == "COMPLETED"
        assert (workspace / ".git").exists()

        head = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert head.returncode == 0
    finally:
        httpd.shutdown()
        httpd.server_close()
