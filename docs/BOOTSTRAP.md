# Bootstrap New Project

Use starter commands to generate a fresh pipeline project.

## Option A: Init scaffold only

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
```

## Option B: Init + apply customization in one step

```bash
agentkit-apply --target ./MyPipeline --name MyPipeline --profile extended --config examples/apply_spec.yaml --force
```

Profiles:
- `minimal`: core scaffold + baseline tests + default docs
- `extended`: minimal + additional customization example

## Apply Spec

Use YAML spec (`examples/apply_spec.yaml`) to override:
- `configs` (`system_profile|skills_index|policy_rules|module_rules|runtime`)
- `templates` (metadata/body/body_append by document id)
- `docs.regenerate` (whether to regenerate starter docs)

## Deterministic Generation

- file copy order is fixed and sorted
- generated docs are created from typed runtime state via fill engine
- existing files are preserved unless `--force` is set

## What Gets Generated

- runtime skeleton in `src/agentkit/runtime/`
- `configs/`
- `docs/templates/`
- `docs/generated/` (with starter docs)
- `skills/`
- `examples/`
- `tests/`
- root `README.md` and `AGENTS.md`

## Customize Downstream

1. Module rules: edit `configs/module_rules.yaml`
2. Skills: edit `configs/skills_index.yaml`
3. Templates: edit `docs/templates/*.md`
4. Output paths: use `load_registry_from_templates(..., output_path_overrides=...)`
5. Runtime behavior: replace `src/agentkit/runtime/layers/*`

See generated `docs/CUSTOMIZATION.md` in each initialized project.
