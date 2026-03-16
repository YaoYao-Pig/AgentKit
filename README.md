[![中文](https://img.shields.io/badge/Language-中文-blue)](README.md) [![English](https://img.shields.io/badge/Language-English-lightgrey)](README.en.md)

# AgentKit Starter

AgentKit Starter 是一个可迁移、可扩展的 Agent Pipeline 脚手架仓库。

它提供：
- 分层 runtime skeleton
- 配置系统（YAML）
- 可填充文档系统（模板 + 生命周期触发 + 更新策略）
- 初始化/迁移/应用命令
- 强制任务执行入口（run/verify）

## 核心命令

- `agentkit-init`：初始化新项目
- `agentkit-migrate`：已有项目非破坏接入
- `agentkit-apply`：初始化后应用定制 spec
- `agentkit-run`：强制通过 Pipeline 运行任务
- `agentkit-verify`：校验任务产物是否齐全

也支持模块命令：

```bash
python -m agentkit run --workspace . --task examples/task.sample.yaml
python -m agentkit verify --workspace . --task-id sample-task-001
```

## 安装

```bash
pip install -e .
```

## 快速开始

### 1) 初始化新项目

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
```

### 2) 迁移已有项目（推荐）

```bash
agentkit-migrate --target . --name ExistingProject --profile minimal
```

### 3) 一步到位初始化 + 定制

```bash
agentkit-apply --target ./MyPipeline --name MyPipeline --profile extended --config examples/apply_spec.yaml --force
```

### 4) 通过强制入口运行任务

```bash
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## 任务规范（Task Spec）

示例文件：`examples/task.sample.yaml`

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

## 自定义工具接入（Adapter）

你可以自己写 Python/Shell 工具脚本，然后在 `configs/skills_index.yaml` 声明绑定：

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

当 Planner 输出对应 `action_type` 时，Dispatcher 会自动路由到 adapter。

## 上下文选择器（Context Selector）

用于控制上下文大小，避免全量文档污染模型输入。

```python
from agentkit.runtime.context_selector import ContextSelector, ContextSelectionRequest

selector = ContextSelector(max_chars_per_file=1200)
result = selector.select(ContextSelectionRequest(base_dir='.', task_type='feature', goal='x', module_hints=['runtime']))
```

CLI 示例：

```bash
python examples/context_selection_demo.py
```

## 给 Agent 的提示词（强制入口）

```text
请按 AgentKit 强制入口执行本任务：
1) 先运行 agentkit-run --workspace . --task <task.yaml>
2) 再运行 agentkit-verify --workspace . --task-id <task-id>
3) 输出 .agentkit/state、.agentkit/runs、.agentkit/context 和 docs/generated 的产物清单
4) 未通过 verify 前，不视为任务完成
```

## 参考文档

- `docs/BOOTSTRAP.md`
- `docs/STARTER.md`
- `docs/EXAMPLE_GENERATED_OUTPUT.md`

## 开发与测试

```bash
python -m pytest
```

## License

MIT（建议补充根目录 `LICENSE` 文件）
