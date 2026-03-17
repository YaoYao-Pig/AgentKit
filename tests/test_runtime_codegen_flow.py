import json
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agentkit.config.models import SkillConfig, SkillsIndexConfig
from agentkit.runtime.dispatcher import SkillDispatcherExecutor
from agentkit.runtime.layers.validation import SimpleValidator
from agentkit.runtime.models import Action, PipelineState, PolicyDecision, TaskStatus


class _LlmStubHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        data = json.loads(body)
        response = {
            "status": "success",
            "summary": "stub generated patches",
            "patches": [
                {
                    "path": "src/generated_from_llm.txt",
                    "mode": "overwrite",
                    "content": f"model={data.get('model')}",
                }
            ],
        }
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_llm_http_adapter_and_file_patch_adapter(tmp_path: Path) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _LlmStubHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = httpd.server_address
        endpoint = f"http://{host}:{port}/v1/generate"

        skills = SkillsIndexConfig(
            skills={
                "llm_codegen": SkillConfig(
                    purpose="call llm",
                    adapter="llm_http",
                    static_params={"endpoint": endpoint, "model": "stub-model"},
                ),
                "apply_generated_patch": SkillConfig(
                    purpose="apply patch",
                    adapter="file_patch",
                ),
            }
        )
        executor = SkillDispatcherExecutor.from_skills_index(
            skills,
            workspace_root=str(tmp_path),
            allowed_paths=["src/"],
        )

        state = PipelineState(task_id="codegen-1", status=TaskStatus.EXECUTING)

        llm_result = executor.execute(
            Action(id="a1", action_type="llm_codegen", params={"prompt": "add file"}),
            state,
        )
        assert llm_result.status == "success"

        patches = llm_result.output["response"]["patches"]
        apply_result = executor.execute(
            Action(id="a2", action_type="apply_generated_patch", params={"patches": patches}),
            state,
        )
        assert apply_result.status == "success"
        generated = tmp_path / "src" / "generated_from_llm.txt"
        assert generated.exists()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_file_patch_and_validator_gate_paths() -> None:
    validator = SimpleValidator(
        blocked_action_types=set(),
        review_action_types={"llm_codegen"},
        allowed_paths=["src/", "docs/"],
    )
    state = PipelineState(task_id="policy-1")

    review_action = Action(id="r1", action_type="llm_codegen", params={"prompt": "x"})
    review_result = validator.pre_check(review_action, state)
    assert review_result.decision == PolicyDecision.REQUIRE_REVIEW

    denied_action = Action(
        id="d1",
        action_type="apply_generated_patch",
        params={"patches": [{"path": "README.md", "mode": "overwrite", "content": "x"}]},
    )
    denied = validator.pre_check(denied_action, state)
    assert denied.decision == PolicyDecision.DENY

    allowed_action = Action(
        id="ok1",
        action_type="apply_generated_patch",
        params={"patches": [{"path": "src/ok.txt", "mode": "overwrite", "content": "x"}]},
    )
    allowed = validator.pre_check(allowed_action, state)
    assert allowed.decision == PolicyDecision.ALLOW
