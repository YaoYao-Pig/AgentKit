[![中文](https://img.shields.io/badge/Language-中文-blue)](README.md) [![English](https://img.shields.io/badge/Language-English-lightgrey)](README.en.md)

# AgentKit Starter

AgentKit Starter 是一个可迁移、可扩展的 Agent Pipeline 脚手架。

## 你现在能得到什么

- 统一任务入口：`agentkit-run`
- 任务产物校验：`agentkit-verify`
- 状态与审计产物：`.agentkit/context|state|runs`
- 自动文档更新：`docs/generated/*`
- 可插拔工具能力：`skills_index.yaml` + adapter dispatcher

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## 强制入口说明

- `agentkit-run`：必须通过它启动任务执行链
- `agentkit-verify`：必须通过它校验任务产物是否齐全
- 推荐在 CI 中把 `agentkit-verify` 设为必过项（仓库已提供 `.github/workflows/agentkit-ci.yml`）

## Task Spec（实现驱动字段）

示例：`examples/task.sample.yaml`

关键字段：
- `affected_files`
- `validation_checklist`
- `rollback_plan`
- `risk_points`

这些字段会进入状态与 `docs/generated/task_model.md`，用于约束实现路线。

## 自定义工具（Adapter）

在 `configs/skills_index.yaml` 声明 skill：

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

## 上下文选择器

使用 `ContextSelector` 控制上下文规模，避免全量文档污染模型输入。

```bash
python examples/context_selection_demo.py
```

## 其他命令

- `agentkit-migrate`：已有项目非破坏接入
- `agentkit-apply`：初始化并应用定制 spec

## 测试

```bash
python -m pytest
```
