[![中文](https://img.shields.io/badge/Language-中文-lightgrey)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README.en.md)

# AgentKit Starter

AgentKit Starter is not a business app. It is a reusable scaffold for building governed, auditable agent execution pipelines.

Its main purpose is not to run more commands. Its purpose is to turn agent work from chat-only behavior into a reproducible engineering process.

## Why this process matters

In real projects, pure chat-driven agent workflows usually fail in three ways:
- same request, different execution path, poor reproducibility
- hard to reconstruct what changed and why from chat history alone
- rules exist only in prompts, with no system-level enforcement

AgentKit addresses this by providing:
- **Enforced entry points**: tasks enter a run/verify flow instead of free-form edits
- **Structured traceability**: state, decisions, docs, and verification outputs are persisted
- **Controlled execution**: model calls, tool calls, and file writes pass policy gates

In short: this is an agent governance layer, not a one-off prompt trick.

## Role in a real project

- **Human**: provides goals, constraints, acceptance criteria
- **Interactive agent**: interprets requirements, prepares task specs, calls AgentKit API
- **AgentKit runtime**: state machine progression, policy checks, execution dispatch, docs updates
- **Adapters**: concrete execution bridges (shell/python/LLM gateway/file patch)
- **CI**: final gatekeeper

## Quick start

```bash
pip install -e .
agentkit-doctor --workspace . --strict
```

### Minimal CLI flow

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## API-enforced mode (recommended)

## 1) Configure the API server

Edit `configs/runtime.yaml`:

```yaml
max_steps: 6
default_action_type: mock_action
api_host: 127.0.0.1
api_port: 8787
require_api_token: true
api_token: dev-agentkit-token
```

\nStrict API codegen mode (recommended for team enforcement):\n\n```yaml\nstrict_codegen_mode: true\nllm_healthcheck_required: true\nllm_endpoint_timeout_sec: 3\nllm_api_key_env: AGENTKIT_LLM_API_KEY\n```\n\nWhen enabled, AgentKit blocks execution unless:\n- action resolves to `llm_codegen`\n- `apply_generated_patch` skill exists\n- `AGENTKIT_LLM_API_KEY` is set\n- (optional) endpoint reachability check passes\n\nField meanings:
- `api_host` / `api_port`: bind address for AgentKit server
- `require_api_token`: enforce authenticated API calls
- `api_token`: server-side token for request authorization (use env-injection in production)
- `api_log_to_file` / `api_log_file`: persistent service logs (default `.agentkit/logs/agentkit-serve.log`)

\nFor more detailed logs (auth failures, run/verify route handling, LLM forwarding summaries), use:\n\n```bash\nagentkit-serve --workspace . --log-level DEBUG\n```\n## 2) Start the service

```bash
agentkit-serve --workspace .
```

Endpoints:
- `GET /health`
- `POST /v1/tasks/run`
- `POST /v1/tasks/verify`

## 3) Call the API

Example script:

```bash
python examples/api_enforced_demo.py
```

Or call directly:

```bash
curl -X POST "http://127.0.0.1:8787/v1/tasks/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-agentkit-token" \
  -d '{"task":"examples/task.sample.yaml"}'
```

```bash
curl -X POST "http://127.0.0.1:8787/v1/tasks/verify" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-agentkit-token" \
  -d '{"task_id":"sample-task-001"}'
```

## Correct interaction pattern (human <-> agent)

Recommended contract:

1. Give business objectives and constraints, not direct raw line-edit instructions.
2. Require the agent to prepare/update task specs first.
3. Require execution via `/v1/tasks/run` through `agentkit-serve`.
4. Require `/v1/tasks/verify` before completion.
5. Require output with changed files, evidence, risks, rollback notes.

Reusable prompt template:

```text
Execute this request using the AgentKit protocol:
1) Create/update task spec with affected_files, validation_checklist, rollback_plan, risk_points
2) Execute through /v1/tasks/run via agentkit-serve
3) Verify through /v1/tasks/verify
4) Return changed files, validation evidence, and residual risks
Do not bypass AgentKit with direct uncontrolled edits.
```

## Code generation loop (LLM -> Patch -> guarded write)

You can now run this chain:
- `llm_http`: call your model gateway and receive structured JSON
- `file_patch`: apply file writes from structured patch lists
- `module_rules.allowed_paths`: deny out-of-scope write targets

Default skill mapping example (`configs/skills_index.yaml`):

```yaml
skills:
  llm_codegen:
    purpose: call a model API to generate structured code patch proposals
    adapter: llm_http
    static_params:
      endpoint: "http://127.0.0.1:9000/v1/generate"
      model: "generic-codegen"
      api_key_env: "AGENTKIT_LLM_API_KEY"

  apply_generated_patch:
    purpose: apply structured patch operations under module rules
    adapter: file_patch
```

See `examples/task.codegen.sample.yaml` for a starter task spec.

## Policy and safety boundaries

Control surfaces:
- `configs/policy_rules.yaml`
  - `blocked_action_types`: hard deny
  - `review_action_types`: require human review branch
- `configs/module_rules.yaml`
  - `allowed_paths`: file write whitelist
- `SimpleValidator`
  - pre-check: action type and path safety
  - post-check: execution status

Recommended practice:
- place high-risk actions in `review_action_types`
- keep `allowed_paths` narrow
- enforce `agentkit-verify` in CI

## Artifacts and traceability

After each run:
- `.agentkit/context/*.json`: context selection reports
- `.agentkit/state/*.json`: state machine snapshots
- `.agentkit/runs/*.json`: run reports
- `docs/generated/*.md`: handoff docs (task_model/decision_log/handoff_note/...)

These artifacts form your execution audit chain.

## Debug log triage (for adjacent-agent troubleshooting)\n\nDefault log file: `.agentkit/logs/agentkit-serve.log`\n\nRecommended startup for debugging:\n\n```bash\nagentkit-serve --workspace . --log-level DEBUG\n```\n\nPrioritize these log lines:\n- `[request_id] POST /v1/tasks/run`: request reached the service\n- `unauthorized`: token/header mismatch\n- `strict_codegen_mode` errors: hard gate blocked execution\n- `llm_http request/response`: confirms remote writer API was actually called\n- `strict codegen patches applied`: confirms patch ledger-backed write was applied\n\nIf verify fails, inspect:\n- `.agentkit/patches/<task_id>.json` (API patch evidence)\n- `.agentkit/runs/<task_id>.json` (execution summary)\n- git changes under `src/` or `tests/` that are not present in patch ledger\n\n## Common anti-patterns

- Skipping run/verify and relying only on chat discipline
- Committing plaintext tokens into repo
- Setting `allowed_paths` too broad
- Reviewing chat summaries without checking persisted artifacts

## Cleanup for previously adopted projects

If you have run AgentKit multiple times in the same repository, clean old artifacts before re-running.

Safe default cleanup (recommended): remove runtime artifacts under `.agentkit/` only:

```bash
agentkit-clean --target . --scope runtime
```

Scopes:
- `runtime`: remove `.agentkit/` (default)
- `docs`: remove generated files in `docs/generated/` except `.gitkeep`
- `migration`: remove `*.starter.*` and `docs/MIGRATION_REPORT.md`
- `all`: all scopes above

Preview first without deleting:

```bash
agentkit-clean --target . --scope all --dry-run
```

Notes:
- The command is designed to remove AgentKit artifacts, not business source code.
- Still recommended to run `--dry-run` before actual deletion.
## Other commands

- `agentkit-migrate`: non-destructive adoption for existing projects
- `agentkit-apply`: initialize and apply customization spec
- `python examples/context_selection_demo.py`: context control demo

## Existing Project Adoption Example

Assume you already have a long-running repo `LegacyProject/` and want to adopt AgentKit with minimal risk.

1. Run non-destructive migration from repo root:

```bash
agentkit-migrate --target . --name LegacyProject --profile minimal
```

2. Review newly added scaffold artifacts (should not overwrite business code):
- `src/agentkit/`
- `configs/`
- `docs/templates/`
- `docs/generated/`
- `examples/`
- `tests/`
- `.github/workflows/agentkit-ci.yml`

3. Tighten boundaries for your repository:
- `configs/module_rules.yaml`: restrict writeable paths
- `configs/policy_rules.yaml`: move risky actions to review
- `configs/skills_index.yaml`: point `llm_codegen.endpoint` to your model gateway

4. Start API mode and validate:

```bash
agentkit-serve --workspace . --require-token --token <your-token>
python examples/api_enforced_demo.py
```

5. Enforce in CI (or keep the provided gate):
- `agentkit-verify` must pass
- fail if required `.agentkit` / `docs/generated` artifacts are missing

Rollback path (if you want to temporarily remove adoption):
- remove `src/agentkit`, `configs`, `docs/templates`, `docs/generated`, `.agentkit`
- remove AgentKit steps from CI
- business code should remain unaffected (sidecar-style migration)
## Tests

```bash
python -m pytest
```

Baseline includes schema, document rendering, registry loading, runtime happy/replan paths, API server, and codegen-flow tests.






