from __future__ import annotations

import json
import urllib.request


def _post(url: str, payload: dict, token: str) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    base = "http://127.0.0.1:8787"
    token = "dev-agentkit-token"

    run_result = _post(f"{base}/v1/tasks/run", {"task": "examples/task.sample.yaml"}, token)
    print("Run result:")
    print(json.dumps(run_result, ensure_ascii=False, indent=2))

    verify_result = _post(
        f"{base}/v1/tasks/verify",
        {"task_id": run_result["task_id"]},
        token,
    )
    print("\nVerify result:")
    print(json.dumps(verify_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
