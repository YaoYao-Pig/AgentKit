[![中文](https://img.shields.io/badge/Language-中文-lightgrey)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README.en.md)

# AgentKit Starter

AgentKit Starter is a migration-friendly scaffold for Agent Pipeline projects.

## What you get

- Enforced task entry: `agentkit-run`
- Artifact gate: `agentkit-verify`
- Runtime artifacts: `.agentkit/context|state|runs`
- Automatic docs updates: `docs/generated/*`
- Pluggable tool execution: `skills_index.yaml` + adapter dispatcher

## Install

```bash
pip install -e .
```

## Quick Start

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## Enforced execution model

- `agentkit-run` is the required runtime task entry
- `agentkit-verify` is the required artifact gate
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
  run_tests:
    adapter: shell
    command: "python -m pytest -q"

  python_health_check:
    adapter: python_callable
    module: agentkit.runtime.sample_skills
    function: health_check
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
