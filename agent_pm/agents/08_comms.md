---
stage: 08
purpose: 测量前锁定谁收什么、口径到哪；对外不得宽于四选一
entry_conditions:
  - G6 已过
read_sources:
  - 合同/核心合同.md §1
  - 流程/08 沟通/AGENT.md
human_inputs:
  - 干系人名单
  - 沟通矩阵本案稿
agent_writable_fields:
  - stakeholder_decision
  - comms_cadence
  - comms_bound
  - comms_api_not_primary
derived_fields: （无）
hard_rules:
  - comms_bound 含"不得宽于四选一"或"四选一"
  - 决策人只收四选一，不把 API 附表当主表
  - 诊断阶段不得预告"优化后会涨"
  - 不得宽于 sop_stage 允许集
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 08_沟通矩阵
  - 08_干系人
gate: G7
handoff_to:
  - 下一站 stage 03
  - 必须读字段: stakeholder_decision, comms_cadence, comms_bound, comms_api_not_primary
must_not:
  - 外加 L1
  - 把客户全称写进通用模板
  - 把真名写进看板原件
---

# 08 沟通 Agent

G6 之后、测量之前锁定谁收什么、话说到哪。apply 后停到 G7。

可写：`stakeholder_decision` `comms_cadence` `comms_bound`。

必须：
- `comms_bound` 含「不得宽于四选一」或「四选一」。
- 决策人 `stakeholder_decision` 只收四选一结论，不把 API 附表当主表。
- 诊断阶段不得预告「优化后会涨」。

产出：`agent_pm/cases/{本案}/out/08_沟通矩阵.md`。05/06 过程纪要另写 `out/08_纪要.md`，口径仍受本步约束。
