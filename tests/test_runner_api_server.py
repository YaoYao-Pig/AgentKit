import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from agentkit.runner.server import ApiServerSettings, create_http_server
from agentkit.starter.init import initialize_starter_project


def _post_json(url: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body)


def test_api_server_enforces_token_and_runs_pipeline(tmp_path: Path) -> None:
    workspace = tmp_path / "api_project"
    initialize_starter_project(target_dir=workspace, project_name="Api Demo", profile_name="minimal", force=True)

    settings = ApiServerSettings(
        workspace=str(workspace),
        host="127.0.0.1",
        port=0,
        require_api_token=True,
        api_token="test-token",
    )
    handle = create_http_server(settings)
    thread = threading.Thread(target=handle.httpd.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = handle.httpd.server_address
        run_url = f"http://{host}:{port}/v1/tasks/run"
        verify_url = f"http://{host}:{port}/v1/tasks/verify"

        unauthorized_status, _ = _post_json(run_url, {"task": "examples/task.sample.yaml"})
        assert unauthorized_status == 401

        run_status, run_payload = _post_json(
            run_url,
            {"task": "examples/task.sample.yaml"},
            token="test-token",
        )
        assert run_status == 200
        assert run_payload["task_id"] == "sample-task-001"

        verify_status, verify_payload = _post_json(
            verify_url,
            {"task_id": "sample-task-001"},
            token="test-token",
        )
        assert verify_status == 200
        assert verify_payload["ok"] is True
        assert verify_payload["missing"] == []
    finally:
        handle.httpd.shutdown()
        handle.httpd.server_close()
        thread.join(timeout=5)
