[![中文](https://img.shields.io/badge/Language-中文-lightgrey)](README.md) [![English](https://img.shields.io/badge/Language-English-blue)](README.en.md)

# AgentKit Starter

AgentKit Starter is a migration-friendly, extensible scaffold for Agent Pipeline projects.

It is not a business application.
It is not tied to a single vendor.
It does not assume a single runtime.

It provides reusable foundations:
- Layered runtime skeleton
- YAML-based configuration system
- Agent-fillable document system (templates + lifecycle triggers + update strategies)
- Initialization, migration, and one-step apply commands
- Examples and tests

## Core Capabilities

- Six runtime layers: Identity / Capability / Planning / Execution / Validation / State
- Document subsystem: registry + metadata schema + markdown loader + renderer + writer + fill engine
- Update strategies: `overwrite` / `append` / `snapshot` / `versioned`
- Starter profiles: `minimal` / `extended`
- Init command: `agentkit-init`
- Migration command: `agentkit-migrate` (safe adoption for existing projects)
- One-step command: `agentkit-apply` (initialize + apply customization spec)

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

### 4) Validate in the generated project

```bash
cd MyPipeline
pip install -e .
python -m pytest
python examples/mock_pipeline.py
```

## Prompt Templates for Agents

You can copy and send these prompts directly to your coding agent.

### Init Only

```text
Please initialize a new project with AgentKit:
- target: ./MyPipeline
- name: MyPipeline
- profile: minimal

Please run automatically:
1) pip install -e .
2) agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
3) In MyPipeline, run python -m pytest and python examples/mock_pipeline.py
4) Summarize generated structure and key files
```

### Migrate Existing Project (safe mode)

```text
Please migrate this existing project to AgentKit in non-destructive mode:
- target: .
- name: ExistingProject
- profile: minimal

Please run automatically:
1) pip install -e .
2) agentkit-migrate --target . --name ExistingProject --profile minimal
3) Keep existing README.md and AGENTS.md unchanged
4) Generate *.starter.* sidecar files and docs/MIGRATION_REPORT.md
5) Summarize new structure, conflicts, and recommended merge steps
```

### One-Step Init + Apply

```text
Please initialize and customize a new project with AgentKit in one run:
- target: ./MyPipeline
- name: MyPipeline
- profile: extended
- apply spec: examples/apply_spec.yaml

Please run automatically:
1) pip install -e .
2) agentkit-apply --target ./MyPipeline --name MyPipeline --profile extended --config examples/apply_spec.yaml --force
3) In MyPipeline, run python -m pytest and python examples/mock_pipeline.py
4) Summarize what configs/templates were updated and what docs were generated
```

## Commands

### `agentkit-init`

```bash
agentkit-init --target <dir> --name <project-name> [--profile minimal|extended] [--force]
```

What it does:
- Generates standard project structure
- Copies runtime/config/template/example/test scaffolding
- Generates default `README.md` / `AGENTS.md`
- Generates starter docs in `docs/generated/`

### `agentkit-migrate`

```bash
agentkit-migrate --target <existing-project-dir> [--name <project-name>] [--profile minimal|extended] [--no-sidecars]
```

What it does:
- Adds AgentKit structure into an existing project without overwriting existing files by default
- Generates `*.starter.*` sidecar files for key conflicts
- Writes `docs/MIGRATION_REPORT.md` for migration audit and next steps

### `agentkit-apply`

```bash
agentkit-apply --target <dir> --name <project-name> [--profile minimal|extended] [--config <yaml>] [--force]
```

What it does:
- Runs init first
- Applies YAML spec overrides for configs/templates
- Regenerates starter docs automatically

## Apply Spec

Reference file: `examples/apply_spec.yaml`

Supported top-level fields:
- `configs`: override `system_profile|skills_index|policy_rules|module_rules|runtime`
- `templates`: override metadata/body by document id
- `docs.regenerate`: whether to regenerate `docs/generated/*`

Example:

```yaml
configs:
  module_rules:
    allowed_paths: ["src/", "docs/"]

templates:
  handoff_note:
    metadata:
      output_path: docs/generated/custom_handoff.md
    body_append: |
      ## Extra
      - team: platform

docs:
  regenerate: true
```

## Generated Project Layout

```text
<project>/
  src/agentkit/
    runtime/
    docs/
    config/
  configs/
  docs/
    templates/
    generated/
  skills/
  examples/
  tests/
  README.md
  AGENTS.md
```

## How Downstream Teams Customize

1. Module boundaries and dependency rules: `configs/module_rules.yaml`
2. Skill catalog and risk levels: `configs/skills_index.yaml`
3. Document templates and lifecycle metadata: `docs/templates/*.md`
4. Document output paths: template `output_path` or registry override
5. Runtime behavior: replace `src/agentkit/runtime/layers/*`

See also:
- `docs/BOOTSTRAP.md`
- `docs/STARTER.md`
- `docs/EXAMPLE_GENERATED_OUTPUT.md`

## Development and Tests

```bash
python -m pytest
```

Current test coverage includes:
- schema validation
- registry loading
- document rendering
- fill engine
- runtime happy path + replan branch
- starter init/apply/migrate flow

## Design Principles

- Config-driven behavior over hardcoding
- Decoupled modules, avoid circular dependencies
- Typed schemas over loose dictionaries
- Keep policy/skill/store/renderer/registry pluggable
- No domain-specific business logic in core

## License

MIT (recommended: add a `LICENSE` file at project root for GitHub publishing)
