[![中文](https://img.shields.io/badge/Language-中文-blue)](README.md) [![English](https://img.shields.io/badge/Language-English-lightgrey)](README.en.md)

# AgentKit Starter

AgentKit Starter 不是一个业务应用，而是一个可复用的 Agent 执行框架脚手架。

它的核心目标不是“帮你多跑几条命令”，而是把 Agent 的工作从“聊天行为”升级成“可审计、可复现、可治理”的工程流程。

## 这套流程的意义（先回答为什么）

在真实项目里，纯对话式 Agent 常见问题是：
- 同样需求，执行路径不稳定，结果不可复现。
- 只看聊天记录，无法准确还原“改了什么、为什么改、如何回滚”。
- 规则只在提示词里，缺少系统级强制。

AgentKit 解决的是这三件事：
- **强制入口**：任务必须进入 `run/verify` 链路，不靠 Agent 自觉。
- **结构化留痕**：状态、决策、文档、验证结果都落盘。
- **可控执行**：模型调用、工具调用、文件写入都经过配置和策略门禁。

一句话：你得到的是“可治理的 Agent 工程系统”，不是“一次性的提示词技巧”。

## AgentKit 在项目中的角色

- **你（人）**：给业务目标、边界、验收标准。
- **交互式 Agent**：理解需求、组织任务、调用 AgentKit API。
- **AgentKit Runtime**：负责状态机推进、策略校验、执行调度、文档更新。
- **Adapter 层**：对接 shell / python / LLM 网关 / file patch 等具体执行能力。
- **CI**：最终门禁（没有产物、没有验证，不允许通过）。

## 快速开始

```bash
pip install -e .
```

### CLI 最小链路

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## API 强制模式（推荐生产使用）

## 1) 配置 API 服务

编辑 `configs/runtime.yaml`：

```yaml
max_steps: 6
default_action_type: mock_action
api_host: 127.0.0.1
api_port: 8787
require_api_token: true
api_token: dev-agentkit-token
```

字段说明：
- `api_host` / `api_port`：AgentKit 服务监听地址。
- `require_api_token`：是否强制鉴权。
- `api_token`：服务端验签 token（建议在生产中改为环境注入，不要明文提交）。

## 2) 启动服务

```bash
agentkit-serve --workspace .
```

启动后会提供接口：
- `GET /health`
- `POST /v1/tasks/run`
- `POST /v1/tasks/verify`

## 3) 调用接口

示例脚本：

```bash
python examples/api_enforced_demo.py
```

或直接调用：

```bash
curl -X POST "http://127.0.0.1:8787/v1/tasks/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-agentkit-token" \
  -d '{"task":"examples/task.sample.yaml"}'
```

```bash
curl -X POST "http://127.0.0.1:8787/v1/tasks/verify" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-agentkit-token" \
  -d '{"task_id":"sample-task-001"}'
```

## 正确的交互模式（你和 Agent 应该怎么说）

推荐把对话协议固定为：

1. 你只给“业务目标 + 约束 + 验收”，不要直接说“去改哪个文件第几行”。
2. 要求 Agent 先建任务，再执行：
   - 先生成/更新 task spec
   - 再调用 `/v1/tasks/run`
3. 要求 Agent 结束前必须调用 `/v1/tasks/verify`。
4. 要求 Agent 输出：
   - 改动文件清单
   - 验证证据
   - 风险与回滚点

可直接复用的提示模板：

```text
请按 AgentKit 协议执行本需求：
1) 先更新或创建 task spec（含 affected_files / validation_checklist / rollback_plan / risk_points）
2) 通过 agentkit-serve 调用 /v1/tasks/run 执行
3) 执行后调用 /v1/tasks/verify
4) 输出变更清单、验证结果、剩余风险
不要绕过 AgentKit 直接裸改代码。
```

## 代码生成闭环（LLM -> Patch -> 受控写入）

你现在可以走这条链路：
- `llm_http`：调用你的模型网关，产出结构化 JSON（可包含 patch 提议）。
- `file_patch`：根据 patch 写文件。
- `module_rules.allowed_paths`：限制可写路径，越界直接 deny。

默认技能配置示例（`configs/skills_index.yaml`）：

```yaml
skills:
  llm_codegen:
    purpose: call a model API to generate structured code patch proposals
    adapter: llm_http
    static_params:
      endpoint: "http://127.0.0.1:9000/v1/generate"
      model: "generic-codegen"
      api_key_env: "AGENTKIT_LLM_API_KEY"

  apply_generated_patch:
    purpose: apply structured patch operations under module rules
    adapter: file_patch
```

任务样例见：`examples/task.codegen.sample.yaml`。

## 策略与安全边界

关键控制面：
- `configs/policy_rules.yaml`
  - `blocked_action_types`：直接拒绝。
  - `review_action_types`：进入人工审核分支。
- `configs/module_rules.yaml`
  - `allowed_paths`：白名单路径。
- `SimpleValidator`
  - pre-check：动作类型 + 路径安全。
  - post-check：执行结果状态。

建议：
- 把高风险 skill 放入 `review_action_types`。
- 把 `allowed_paths` 收紧到必要目录。
- 在 CI 中强制 `agentkit-verify`。

## 产物与可追溯性

运行后会生成：
- `.agentkit/context/*.json`：上下文选择报告。
- `.agentkit/state/*.json`：状态机执行状态。
- `.agentkit/runs/*.json`：运行报告。
- `docs/generated/*.md`：可交接文档（task_model/decision_log/handoff_note 等）。

这些产物一起构成“任务审计链”。

## 常见误区

- 误区 1：只让 Agent 对话，不要求 run/verify。
  - 结果：流程不可追踪，约束难落地。
- 误区 2：把 token 直接提交到仓库。
  - 结果：凭据泄露风险。
- 误区 3：`allowed_paths` 设得太宽。
  - 结果：边界失效，写入风险扩大。
- 误区 4：只看聊天总结，不看产物文件。
  - 结果：交接困难、复盘困难。

## 其他命令

- `agentkit-migrate`：已有项目非破坏接入。
- `agentkit-apply`：初始化并应用自定义 spec。
- `python examples/context_selection_demo.py`：上下文控制示例。

## 真实项目接入示例（从已有仓库迁移）

假设你有一个已经开发中的仓库 `LegacyProject/`，希望最小代价接入 AgentKit。

1. 在旧仓库根目录执行迁移（非破坏）：

```bash
agentkit-migrate --target . --name LegacyProject --profile minimal
```

2. 检查新增目录与文件（通常会新增，不会覆盖你的业务代码）：
- `src/agentkit/`
- `configs/`
- `docs/templates/`
- `docs/generated/`
- `examples/`
- `tests/`
- `.github/workflows/agentkit-ci.yml`

3. 按你的仓库边界收紧策略：
- `configs/module_rules.yaml` 只保留允许写入的路径
- `configs/policy_rules.yaml` 把高风险动作放入 review
- `configs/skills_index.yaml` 把 `llm_codegen.endpoint` 改成你的模型网关

4. 启动 API 模式并验证：

```bash
agentkit-serve --workspace . --require-token --token <your-token>
python examples/api_enforced_demo.py
```

5. 在 CI 增加门禁（或保留模板中的门禁）：
- 必须通过 `agentkit-verify`
- 缺少 `.agentkit` / `docs/generated` 核心产物即失败

回滚方式（如果你想暂时撤销接入）：
- 移除 `src/agentkit`、`configs`、`docs/templates`、`docs/generated`、`.agentkit`
- 移除 CI 里的 AgentKit 步骤
- 业务代码不应受影响（迁移流程默认是 sidecar 式接入）
## 测试

```bash
python -m pytest
```

当前基线包含：schema、文档渲染、注册表加载、runtime happy path/replan、API 服务与 codegen flow 测试。

