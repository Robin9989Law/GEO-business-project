# Agent 合同卡模板（每阶段一份）

每个阶段（01/02/07/08/03/04/05/06/09/10）都有一份 `agent_pm/agents/0X_*.md`，其头部必须包含以下字段（用 markdown 表格或 YAML frontmatter 任选其一）。`00_orchestrator.md` 与 `10_files.md` 是横切层，沿用相同 schema 但 stage 字段标为「all」或对应 stage。

字段固定（缺一不可）：

| 字段 | 含义 |
|---|---|
| `stage` | 阶段编号（01/02/07/08/03/04/05/06/09/10） |
| `purpose` | 这一阶段为什么存在（不超过 2 句） |
| `entry_conditions` | 进入本阶段必须已满足的条件（gate + 字段列表） |
| `read_sources` | 必读文件：`合同/核心合同.md §X` + `流程/0X .../AGENT.md` + `流程/10 项目文件/规则.md` + 本目录的 2–3 个附件 |
| `human_inputs` | 人需要交什么原始件（路径形态） |
| `agent_writable_fields` | 本阶段 Agent 可写的字段列表（与 `核心合同字段.csv` writer_stage 一致） |
| `derived_fields` | 由本阶段派生但不直写的字段（如 `verdict_4` 派生自 `baseline_verdict_4` + `intervention_need_ids` 等） |
| `hard_rules` | 本阶段硬规则清单（哪些值必须落入哪个集合、哪些 token 禁出现） |
| `quality_dimensions` | Agent 质检维度（5 维：完整 / 准确 / 一致 / 可追溯 / 无泄漏） |
| `formal_outputs` | 本阶段过门后要升正式版的 `doc_id` 列表（必须在 `合同/阶段交付物注册.md` 中已声明） |
| `gate` | 绑定的门（G0/G1/G6/G7/G3/G2/G5/G4/G8） |
| `handoff_to` | 下一站（`stage` + 必读字段） |
| `must_not` | 本 Agent 不得做的事（禁售扩展 + 业务禁越） |

---

## YAML 模板（推荐）

每个 `agent_pm/agents/0X_*.md` 第一行用 `---` 包一段 YAML frontmatter：

```yaml
---
stage: 03
purpose: 冻结 02 已锁字段，采集 App 冷问，出噪声/基线数
entry_conditions:
  - G1 / G6 / G7 已过
  - state.fields.sop_stage, platforms_required, treat_need_ids, holdout_need_ids, primary_endpoint, causal_claim, control_design, success_rule_* 全部已锁
read_sources:
  - 合同/核心合同.md §1
  - 流程/03 测量/AGENT.md
  - 流程/03 测量/项目接口.md
  - 流程/10 项目文件/规则.md
human_inputs:
  - 真机 + 干净号 + 定位切到 {city}
  - App 冷问 txt+截图（按当日清单）
  - 第二人基线 Core 抽检
agent_writable_fields:
  - freeze_id
  - data_grade
  - baseline_verdict_4
derived_fields:
  - measure_isolated
  - config_checksum
hard_rules:
  - 本阶段 verdict_4：诊断/续约可写；冲刺只写 baseline_verdict_4
  - baseline_verdict_4 ∈ {描述基线, 不能下结论}
  - 未冻结不得采
  - 不自动点消费级 App
quality_dimensions:
  - 完整：03 必填全到
  - 准确：coverage_ok、data_grade 与样本一致
  - 一致：冻结平台/need 与 02 一致
  - 可追溯：case_id / freeze_id / config_checksum 全在
  - 无泄漏：客户事实不在 10 资产库
formal_outputs:
  - 03_冻结包
  - 03_环境登记
  - 03_出数报告
gate: G3
handoff_to:
  stage: 04
  must_read_fields: [freeze_id, sop_stage, baseline_verdict_4]
must_not:
  - 写 L1/确认性因果
  - 冲刺本步复测或写最终 verdict_4
  - 把 API 当主表
  - 客户事实进 10 资产库
---
```

## Markdown 表格模板（备选）

```markdown
| 字段 | 值 |
|---|---|
| stage | 03 |
| purpose | 冻结 02 已锁字段，采集 App 冷问，出噪声/基线数 |
| entry_conditions | G1/G6/G7 已过；sop_stage、platforms_required、treat/holdout、primary_endpoint、causal_claim、control_design、success_rule_* 全锁 |
| read_sources | 合同/核心合同.md §1；流程/03 测量/AGENT.md；流程/03 测量/项目接口.md；流程/10 项目文件/规则.md |
| human_inputs | 真机+干净号+定位；App 冷问 txt+截图；第二人基线 Core 抽检 |
| agent_writable_fields | freeze_id, data_grade, baseline_verdict_4 |
| derived_fields | measure_isolated, config_checksum |
| hard_rules | verdict_4 写入规则见 §1；未冻结不得采；不自动点 App |
| quality_dimensions | 完整/准确/一致/可追溯/无泄漏 |
| formal_outputs | 03_冻结包, 03_环境登记, 03_出数报告 |
| gate | G3 |
| handoff_to | 04（须读 freeze_id, sop_stage, baseline_verdict_4） |
| must_not | 写 L1；冲刺本步复测；API 主表；客户事实入资产 |
```

## 与现有提示词的关系

- 现有 `agent_pm/agents/0X_*.md` 是一段"白话提示词"。本卡是它的**结构化头部**。
- 头部之后允许有任意长度的自由文字（白话解释、示例、反例、边界说明）。
- 头部字段必须与 `合同/核心合同.md`、`合同/阶段交付物注册.md` 一一对应；不一致时以这两份为准并改 Agent 头部。
- `entry_conditions` 与 `gate` 是同一件事：进入本步（`entry_conditions`）与过门（`gate`）。两边都填避免歧义。

## 字段所有权

| 字段 | 谁可写 |
|---|---|
| `agent_pm/agents/*.md` 头部 | 编排 + 负责人（不在本卡片内批准） |
| `合同/Agent 合同卡模板.md`（本文件） | 编排 + 负责人复核 |
| `合同/阶段交付物注册.md` `doc_id` 列表 | 编排提，负责人批 |
| `合同/核心合同.md` 字段表 | 负责人批 |

`must_not` 字段是门禁语言；任何 Agent 行为触犯必写 fail 报告。
