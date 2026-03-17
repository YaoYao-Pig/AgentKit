[![中文](https://img.shields.io/badge/Language-中文-blue)](README.md) [![English](https://img.shields.io/badge/Language-English-lightgrey)](README.en.md)

# AgentKit Starter

AgentKit Starter 是一个可迁移、可扩展的 Agent Pipeline 脚手架。

## 你现在能得到什么

- 统一任务入口：`agentkit-run`
- 任务产物校验：`agentkit-verify`
- API 强制入口：`agentkit-serve`
- 状态与审计产物：`.agentkit/context|state|runs`
- 自动文档更新：`docs/generated/*`
- 可插拔工具能力：`skills_index.yaml` + adapter dispatcher（mock/shell/python_callable/llm_http/file_patch）

## 安装

```bash
pip install -e .
```

## 快速开始（CLI）

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## API 强制模式

可选的代码生成闭环：
- `llm_http` 调用你的模型网关产出结构化 patch
- `file_patch` 在 `module_rules.allowed_paths` 约束下写入代码文件

1. 在 `configs/runtime.yaml` 开启：

```yaml
require_api_token: true
api_token: dev-agentkit-token
api_host: 127.0.0.1
api_port: 8787
```

2. 启动 API 服务：

```bash
agentkit-serve --workspace .
```

3. 通过 API 执行任务（示例脚本）：

```bash
python examples/api_enforced_demo.py
```

你也可以直接调用接口：
- `POST /v1/tasks/run` body: `{ "task": "examples/task.sample.yaml" }`
- `POST /v1/tasks/verify` body: `{ "task_id": "sample-task-001" }`
- Header: `Authorization: Bearer <api_token>`

## 与交互式 Agent 的配合

推荐约束方式：
1. 你只给 Agent 业务需求，不直接让它裸改代码。
2. Agent 先生成/更新 task spec 与文档。
3. Agent 必须通过 `agentkit-serve` 调用 `/v1/tasks/run` 执行。
4. Agent 完成后必须调用 `/v1/tasks/verify`。
5. CI 再做二次门禁。

这样可以把“对话”变成“可审计执行链”，而不是仅靠提示词约束。
## 强制入口说明

- `agentkit-run`：CLI 任务入口
- `agentkit-verify`：CLI 产物校验入口
- `agentkit-serve`：API 任务入口（支持 token 鉴权）
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
  llm_codegen:
    adapter: llm_http
    static_params:
      endpoint: "http://127.0.0.1:9000/v1/generate"
      model: "generic-codegen"
      api_key_env: "AGENTKIT_LLM_API_KEY"

  apply_generated_patch:
    adapter: file_patch
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


