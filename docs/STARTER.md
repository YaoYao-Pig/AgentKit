# Starter Baseline (M1)

## Initialize a new project

After installing this package, run:

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
```

Profiles:
- `minimal`: core runtime/docs/config scaffold
- `extended`: minimal + extra customization example

Use `--force` to overwrite existing files.

## Run local example

```bash
python examples/mock_pipeline.py
```

This runs the runtime skeleton, then uses the document fill engine to update documents by lifecycle trigger:
- `task_modeling`
- `postcheck`
- `task_completed`

## Run tests

```bash
python -m pytest
```

## Document lifecycle model

1. Templates are discovered from `docs/templates/*.md`.
2. Front matter metadata is validated into a typed schema.
3. Registry selects documents for a trigger (`created_when` or `updated_when`).
4. Fill engine builds typed context from `Task` + `PipelineState`.
5. Renderer resolves `{{token}}` placeholders.
6. Writer applies update strategy:
   - `overwrite`
   - `append`
   - `snapshot`
   - `versioned`

## Downstream customization

- Change module constraints in `configs/module_rules.yaml`
- Change skill catalog in `configs/skills_index.yaml`
- Change template metadata and body in `docs/templates/*.md`
- Override output paths via registry loader `output_path_overrides`
- Replace `TokenRenderer` with custom renderer
- Replace or extend update strategies in `StrategyRegistry`
- Extend context builders in `RuntimeDocumentFillEngine`
