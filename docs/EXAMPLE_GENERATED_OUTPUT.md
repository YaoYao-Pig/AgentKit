# Example Generated Output

Command used:

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile extended
```

Example top-level output tree:

```text
MyPipeline/
  AGENTS.md
  README.md
  pyproject.toml
  configs/
  docs/
    CUSTOMIZATION.md
    templates/
    generated/
  skills/
  examples/
  src/
    agentkit/
      runtime/
      docs/
      config/
  tests/
```

Generated starter docs in `docs/generated/` include:
- `project_charter.md`
- `task_model.md`
- `decision_log.md`
- `handoff_note.md`
- `risk_register.<timestamp>.md`
- `milestone_report.v1.md`
