[![中文](https://img.shields.io/badge/Language-中文-lightgrey)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README.en.md)

# AgentKit Starter

AgentKit Starter is a migration-friendly, extensible scaffold for Agent Pipeline projects.

It provides:
- layered runtime skeleton
- YAML configuration system
- agent-fillable docs system (templates + lifecycle triggers + update strategies)
- init/migrate/apply commands
- enforced task execution entry (run/verify)

## Core Commands

- `agentkit-init`: initialize a new project
- `agentkit-migrate`: non-destructive adoption for existing projects
- `agentkit-apply`: initialize and apply customization spec
- `agentkit-run`: run a task through enforced pipeline
- `agentkit-verify`: verify required task artifacts

Module command form is also supported:

```bash
python -m agentkit run --workspace . --task examples/task.sample.yaml
python -m agentkit verify --workspace . --task-id sample-task-001
```

## Install

```bash
pip install -e .
```

## Quick Start

### 1) Initialize a new project

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
```

### 2) Migrate an existing project (recommended)

```bash
agentkit-migrate --target . --name ExistingProject --profile minimal
```

### 3) Initialize + customize in one step

```bash
agentkit-apply --target ./MyPipeline --name MyPipeline --profile extended --config examples/apply_spec.yaml --force
```

### 4) Run tasks through enforced entry

```bash
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## Task Spec

Sample file: `examples/task.sample.yaml`

```yaml
id: sample-task-001
goal: Verify the AgentKit runtime pipeline entry works
action:
  type: mock_action
  params:
    note: hello
context:
  module_hints:
    - runtime
```

## Custom Tool Integration (Adapters)

Teams can implement concrete tooling in Python/Shell and register skills in `configs/skills_index.yaml`:

```yaml
skills:
  run_shell_echo:
    adapter: shell
    command: "echo {message}"

  python_health_check:
    adapter: python_callable
    module: agentkit.runtime.sample_skills
    function: health_check
```

When planner emits matching `action_type`, dispatcher routes to the configured adapter.

## Context Selector

Use `ContextSelector` to avoid overloading model context with full repository documents.

```python
from agentkit.runtime.context_selector import ContextSelector, ContextSelectionRequest

selector = ContextSelector(max_chars_per_file=1200)
result = selector.select(ContextSelectionRequest(base_dir='.', task_type='feature', goal='x', module_hints=['runtime']))
```

CLI example:

```bash
python examples/context_selection_demo.py
```

## Prompt Template for Agents (Enforced Entry)

```text
Run this task through AgentKit enforced entry:
1) agentkit-run --workspace . --task <task.yaml>
2) agentkit-verify --workspace . --task-id <task-id>
3) Report artifacts under .agentkit/state, .agentkit/runs, .agentkit/context, and docs/generated
4) Task is not complete until verify passes
```

## References

- `docs/BOOTSTRAP.md`
- `docs/STARTER.md`
- `docs/EXAMPLE_GENERATED_OUTPUT.md`

## Development and Tests

```bash
python -m pytest
```

## License

MIT (recommended: add a root `LICENSE` file)
