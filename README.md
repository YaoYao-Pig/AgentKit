[![中文](https://img.shields.io/badge/Language-中文-blue)](README.md) [![English](https://img.shields.io/badge/Language-English-lightgrey)](README.en.md)

# AgentKit Starter

AgentKit Starter 是一个可迁移、可扩展的 Agent Pipeline 脚手架仓库。

它不是业务应用，不绑定单一厂商，不假设单一运行时。
它提供一套可复用基础：
- 分层 runtime skeleton
- 配置系统（YAML）
- 可填充文档系统（模板 + 生命周期触发 + 更新策略）
- 初始化、迁移与一键应用命令
- 示例与测试

## 核心能力

- Runtime 六层骨架：Identity / Capability / Planning / Execution / Validation / State
- 文档子系统：registry + metadata schema + markdown loader + renderer + writer + fill engine
- 更新策略：`overwrite` / `append` / `snapshot` / `versioned`
- Starter profile：`minimal` / `extended`
- 初始化命令：`agentkit-init`
- 迁移命令：`agentkit-migrate`（已有项目非破坏接入）
- 一步到位命令：`agentkit-apply`（初始化 + 应用定制 spec）

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

### 4) 在生成项目中验证

```bash
cd MyPipeline
pip install -e .
python -m pytest
python examples/mock_pipeline.py
```

## 直接给 Agent 的提示词

你可以把下面提示词直接发给 Agent，让它自动完成初始化或迁移。

### 初始化版（只生成脚手架）

```text
请使用 AgentKit 帮我初始化一个新项目：
- target: ./MyPipeline
- name: MyPipeline
- profile: minimal

请自动执行：
1) pip install -e .
2) agentkit-init --target ./MyPipeline --name MyPipeline --profile minimal
3) 进入 MyPipeline 后运行 python -m pytest 和 python examples/mock_pipeline.py
4) 输出最终生成的目录结构与关键文件说明
```

### 迁移版（已有项目接入）

```text
请把当前已有项目接入 AgentKit，要求非破坏迁移：
- target: .
- name: ExistingProject
- profile: minimal

请自动执行：
1) pip install -e .
2) agentkit-migrate --target . --name ExistingProject --profile minimal
3) 保留现有 README.md / AGENTS.md，不覆盖
4) 生成 *.starter.* 对照文件与 docs/MIGRATION_REPORT.md
5) 输出迁移后新增结构、冲突文件与建议合并步骤
```

### 一步到位版（初始化 + 应用定制）

```text
请使用 AgentKit 一步完成项目初始化和定制：
- target: ./MyPipeline
- name: MyPipeline
- profile: extended
- apply spec: examples/apply_spec.yaml

请自动执行：
1) pip install -e .
2) agentkit-apply --target ./MyPipeline --name MyPipeline --profile extended --config examples/apply_spec.yaml --force
3) 进入 MyPipeline 后运行 python -m pytest 和 python examples/mock_pipeline.py
4) 输出你修改了哪些 config/template，以及生成了哪些 docs
```

## 命令说明

### `agentkit-init`

```bash
agentkit-init --target <dir> --name <project-name> [--profile minimal|extended] [--force]
```

作用：
- 生成标准项目结构
- 拷贝 runtime/config/template/example/tests
- 生成默认 `README.md` / `AGENTS.md`
- 生成 starter 文档到 `docs/generated/`

### `agentkit-migrate`

```bash
agentkit-migrate --target <existing-project-dir> [--name <project-name>] [--profile minimal|extended] [--no-sidecars]
```

作用：
- 在已有项目中补齐 AgentKit 结构（默认不覆盖现有文件）
- 对冲突关键文件生成 `*.starter.*` 对照版本
- 输出 `docs/MIGRATION_REPORT.md` 作为迁移审计与后续清单

### `agentkit-apply`

```bash
agentkit-apply --target <dir> --name <project-name> [--profile minimal|extended] [--config <yaml>] [--force]
```

作用：
- 先执行 init
- 再按 YAML spec 覆盖配置和模板
- 自动重新生成 starter 文档

## Apply Spec（定制规范）

参考文件：`examples/apply_spec.yaml`

支持的顶层字段：
- `configs`: 覆盖 `system_profile|skills_index|policy_rules|module_rules|runtime`
- `templates`: 按文档 id 覆盖 metadata/body
- `docs.regenerate`: 是否重新生成 `docs/generated/*`

示例：

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

## 生成项目结构

初始化后默认包含：

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

## 下游团队如何定制

1. 模块边界与依赖规则：`configs/module_rules.yaml`
2. 技能目录与风险等级：`configs/skills_index.yaml`
3. 文档模板与生命周期：`docs/templates/*.md`
4. 文档输出路径：模板 `output_path` 或 registry override
5. 运行时行为：替换 `src/agentkit/runtime/layers/*`

详见：
- `docs/BOOTSTRAP.md`
- `docs/STARTER.md`
- `docs/EXAMPLE_GENERATED_OUTPUT.md`

## 开发与测试

```bash
python -m pytest
```

当前测试覆盖：
- schema validation
- registry loading
- document rendering
- fill engine
- runtime happy path + replan branch
- starter init/apply/migrate flow

## 设计原则

- 配置驱动优先于硬编码
- 模块解耦，避免循环依赖
- 类型化 schema 优先于松散字典
- 保持 policy/skill/store/renderer/registry 可插拔
- 不引入业务特定逻辑

## License

MIT（如需发布到 GitHub，建议在根目录补充 `LICENSE` 文件）
