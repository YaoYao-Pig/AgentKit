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
agentkit-doctor --workspace . --strict
```

### CLI 最小链路

```bash
agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
cd MyPipeline
pip install -e .
agentkit-run --workspace . --task examples/task.sample.yaml
agentkit-verify --workspace . --task-id sample-task-001
```

## 项目应该放在哪里（目录示例）

很多新用户会卡在“这些命令在哪个目录执行”。下面给两个常见场景。

### 场景 A：你要新建一个项目

建议目录结构：

```text
D:/Work/
  AgentKit/                  # 这个仓库（脚手架源码）
  MyPipelineProject/         # 你生成出来的新项目
```

操作方式：

1. 先进入 AgentKit 仓库执行初始化命令：

```bash
cd D:/Work/AgentKit
agentkit-init --target ../MyPipelineProject --name MyPipelineProject --profile minimal
```

2. 再进入你自己的项目目录执行后续命令：

```bash
cd D:/Work/MyPipelineProject
pip install -e .
agentkit-serve --workspace . --require-token --token dev-agentkit-token
```

关键点：
- `agentkit-init` 在脚手架仓库里运行。
- `agentkit-run / verify / serve` 在目标项目根目录运行。

### 场景 B：你已经有一个现成项目

假设你的旧项目在：

```text
D:/Work/LegacyProject/
```

则直接在该目录执行迁移：

```bash
cd D:/Work/LegacyProject
agentkit-migrate --target . --name LegacyProject --profile minimal
```

迁移后，后续所有 AgentKit 命令都在 `LegacyProject` 根目录执行，不需要再回到脚手架仓库。

### 如何快速确认“我在正确目录”

你只要确认当前目录里至少有这些文件/目录：
- `configs/`
- `docs/templates/`
- `examples/`
- `pyproject.toml`

如果这些不存在，通常说明你不在目标项目根目录。
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

\n强制 API 写码模式（可选但推荐在团队落地时开启）：\n\n```yaml\nstrict_codegen_mode: true\nllm_healthcheck_required: true\nllm_endpoint_timeout_sec: 3\nllm_api_key_env: AGENTKIT_LLM_API_KEY\n```\n\n开启后会强制：\n- action 必须走 `llm_codegen`\n- 必须存在 `apply_generated_patch` skill\n- 必须设置 `AGENTKIT_LLM_API_KEY`\n- （可选）endpoint 不可达时直接阻断\n\n字段说明：
- `api_host` / `api_port`：AgentKit 服务监听地址。
- `require_api_token`：是否强制鉴权。
- `api_token`：服务端验签 token（建议在生产中改为环境注入，不要明文提交）。
- `api_log_to_file` / `api_log_file`：是否写入日志文件（默认 `.agentkit/logs/agentkit-serve.log`）。

\n如果你要看更详细日志（含鉴权失败、run/verify 路径、LLM 转发摘要），可以用：\n\n```bash\nagentkit-serve --workspace . --log-level DEBUG\n```\n## 2) 启动服务

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

## 新手完整实战：先管文档，再调用 API 改代码

下面给你一个可以直接照着走的真实场景。

场景：你有一个前端项目，想把首页按钮文案从“立即开始”改成“开始体验”，并要求全流程留痕。

### Step 0：准备（终端）

在项目根目录执行：

```bash
pip install -e .
agentkit-serve --workspace . --require-token --token dev-agentkit-token
```

说明：
- 这一步会启动 AgentKit API 服务。
- 后续 Agent 不应绕过这个服务直接改代码。

### Step 1：你在终端里对 Agent 下达任务（对话）

你可以直接复制下面这段：

```text
需求：把首页主按钮文案从“立即开始”改为“开始体验”。
约束：只允许修改 src/web/ 下文件；不允许改后端。
验收：
1) 页面按钮文案更新
2) 单元测试通过
3) docs/generated 至少更新 task_model、decision_log、handoff_note

请按 AgentKit 协议执行：
- 先创建或更新 task spec 与文档上下文
- 然后通过 agentkit-serve 调 /v1/tasks/run 执行
- 完成后调 /v1/tasks/verify
- 返回改动文件、验证结果、风险和回滚点
```

### Step 2：Agent 应该先做什么（你要观察这几点）

你不需要懂代码，只要检查 Agent 有没有先做这些：

1. 先更新任务建模信息（task spec）。
2. 明确 `affected_files`、`validation_checklist`、`rollback_plan`、`risk_points`。
3. 先更新文档上下文，而不是直接动业务代码。

如果 Agent 一上来就说“我先改文件”，你应立即打断并要求它先走 AgentKit 协议。

### Step 3：Agent 通过 API 执行（而不是裸改）

标准动作应类似：

- 调用 `POST /v1/tasks/run`
- Header 带 `Authorization: Bearer dev-agentkit-token`
- 请求体带 task 文件路径

你可以让 Agent 显示关键返回字段：
- `task_id`
- `status`
- `state_path`
- `run_report_path`
- `generated_docs`

### Step 4：Agent 必须做验证

标准动作：调用 `POST /v1/tasks/verify`。

你要看到：
- `ok: true`
- `missing: []`

如果 `ok=false`，说明流程不完整，不能算完成。

### Step 5：你如何验收（不需要高代码能力）

你只检查四类结果：

1. 代码结果：按钮文案是否变更。
2. 质量结果：测试是否通过（至少 Agent 给出测试证据）。
3. 过程结果：`.agentkit/state`、`.agentkit/runs` 是否有该任务文件。
4. 文档结果：`docs/generated/task_model.md`、`decision_log.md`、`handoff_note.md` 是否更新。

### Step 6：失败时怎么处理

常见失败与处理：

- 失败 A：`Connection refused`
  - 原因：`agentkit-serve` 没启动。
  - 处理：先启动服务，再让 Agent 重试。

- 失败 B：`401 unauthorized`
  - 原因：token 不一致或没带。
  - 处理：确认 `runtime.yaml` 和请求 Header 使用同一个 token。

- 失败 C：`path is outside allowed_paths`
  - 原因：Agent 想改白名单外路径。
  - 处理：
    1) 若确实不该改，保持拒绝；
    2) 若业务需要，先人工更新 `configs/module_rules.yaml` 再重试。

### Step 7：一条“给 Agent 的纠偏话术”

当 Agent 试图绕过流程时，你可以直接说：

```text
停止直接改代码。先按 AgentKit 执行：
1) 更新任务模型与文档上下文
2) 调 /v1/tasks/run
3) 调 /v1/tasks/verify
4) 再汇总变更与风险
```

这个话术对新手非常有效，因为它把“你该怎么盯流程”变成了可执行清单。
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

## 旧项目清理（AgentKit 产物）

如果你之前在同一个仓库里多次试用 AgentKit，建议在重跑前先清理历史产物。

默认安全清理（推荐）：仅清理运行状态目录 `.agentkit/`：

```bash
agentkit-clean --target . --scope runtime
```

常用范围：
- `runtime`：清理 `.agentkit/`（默认）
- `docs`：清理 `docs/generated/` 下除 `.gitkeep` 外的文件
- `migration`：清理 `*.starter.*` 和 `docs/MIGRATION_REPORT.md`
- `all`：以上全部

先预览不删除：

```bash
agentkit-clean --target . --scope all --dry-run
```

说明：
- 该命令设计为“只清理 AgentKit 产物”，不主动删除你的业务源码。
- 仍建议先 `--dry-run` 看一眼，再执行真实删除。
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







