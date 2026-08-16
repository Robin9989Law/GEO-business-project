---
stage: 07
purpose: 测量前锁定人时与报价范围；不写 L1 入报价；scope 匹配 sop_stage 允许集
entry_conditions:
  - G1 已过
  - sop_stage、platforms_required、need 已锁
read_sources:
  - 合同/核心合同.md §1
  - 流程/07 预算和资源管理/AGENT.md
  - 流程/07 预算和资源管理/工时标准.md
human_inputs:
  - 人手与单价约束
  - 预算表（本案副本）
agent_writable_fields:
  - budget_hours
  - budget_scope
  - quote_excludes_l1
derived_fields: （无）
hard_rules:
  - quote_excludes_l1 = 是
  - budget_scope ⊆ BUDGET_SCOPE_OK[sop_stage]
  - 诊断 budget_scope 禁含"干预/一类证据/改页"
  - 人时按 platforms_required × 激活问法 × 允许窗
  - 单位统一为"人时"
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 07_预算
gate: G6
handoff_to:
  - 下一站 stage 08
  - 必须读字段: budget_hours, budget_scope, quote_excludes_l1
must_not:
  - 把 L1 写入报价
  - 把客户成交价写进通用模板
  - 隐瞒超支
---

# 07 预算 Agent

G1 之后、测量之前锁定人时和报价范围。apply 后停到 G6。

可写：`budget_hours` `budget_scope` `quote_excludes_l1`。

必须：
- `quote_excludes_l1=是`。不得把确认性 L1 写成默认交付。
- `budget_scope` 等于当前 `sop_stage` 允许集。
- 诊断单 `budget_scope` 不得含「干预 / 一类证据 / 改页」。
- 人时按 `platforms_required` × 激活问法 × 允许窗，对照 `流程/07 预算和资源管理/工时标准.md`。

产出：`agent_pm/cases/{本案}/out/07_预算.md`。客户成交价不写进通用模板原件。
