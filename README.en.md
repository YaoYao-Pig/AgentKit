[![中文](https://img.shields.io/badge/Language-中文-lightgrey)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README.en.md)

# AgentKit Starter

AgentKit Starter is a migration-friendly scaffold for Agent Pipeline projects.

## What you get

- Enforced task entry: `agentkit-run`
- Artifact gate: `agentkit-verify`
- API enforced entry: `agentkit-serve`
- Runtime artifacts: `.agentkit/context|state|runs`
- Automatic docs updates: `docs/generated/*`
- Pluggable tool execution: `skills_index.yaml` + adapter dispatcher (mock/shell/python_callable/llm_http/file_patch)

## Install

```bash
pip install -e .
```

## Quick Start (CLI)

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## API Enforced Mode

Optional code-generation loop:
- `llm_http` calls your model gateway and returns structured patches
- `file_patch` applies writes under `module_rules.allowed_paths` guardrails

1. Enable token enforcement in `configs/runtime.yaml`:

```yaml
require_api_token: true
api_token: dev-agentkit-token
api_host: 127.0.0.1
api_port: 8787
```

2. Start the API service:

```bash
agentkit-serve --workspace .
```

3. Drive task execution through API (example):

```bash
python examples/api_enforced_demo.py
```

Direct endpoints:
- `POST /v1/tasks/run` body: `{ "task": "examples/task.sample.yaml" }`
- `POST /v1/tasks/verify` body: `{ "task_id": "sample-task-001" }`
- Header: `Authorization: Bearer <api_token>`

## Working With Interactive Agents

Recommended contract:
1. Give business requirements to the agent, not direct raw file-edit instructions.
2. Agent first generates/updates task spec and docs artifacts.
3. Agent must call `/v1/tasks/run` through `agentkit-serve`.
4. Agent must call `/v1/tasks/verify` before completion.
5. CI performs final enforcement.

This turns chat-driven work into an auditable execution chain instead of prompt-only discipline.
## Enforced execution model

- `agentkit-run` is the CLI runtime task entry
- `agentkit-verify` is the CLI artifact gate
- `agentkit-serve` is the API runtime gate with token auth
- CI should enforce verify as required (workflow included: `.github/workflows/agentkit-ci.yml`)

## Task Spec (implementation-driving fields)

See `examples/task.sample.yaml`.

Key fields:
- `affected_files`
- `validation_checklist`
- `rollback_plan`
- `risk_points`

These fields are persisted and rendered into `docs/generated/task_model.md`.

## Custom tools (Adapters)

Declare skills in `configs/skills_index.yaml`:

```yaml
skills:
  llm_codegen:
    adapter: llm_http
    static_params:
      endpoint: "http://127.0.0.1:9000/v1/generate"
      model: "generic-codegen"
      api_key_env: "AGENTKIT_LLM_API_KEY"

  apply_generated_patch:
    adapter: file_patch
```

## Context Selector

Use `ContextSelector` to control context size and relevance.

```bash
python examples/context_selection_demo.py
```

## Other commands

- `agentkit-migrate`: non-destructive adoption for existing projects
- `agentkit-apply`: initialize and apply customization spec

## Tests

```bash
python -m pytest
```


