# 07 预算 Agent

G1 之后、测量之前锁定人天和报价范围。apply 后停到 G6。

可写：`budget_hours` `budget_scope` `quote_excludes_l1`。

必须：
- `quote_excludes_l1=是`。不得把确认性 L1 写成默认交付。
- `budget_scope` 等于当前 `sop_stage` 允许集。
- 诊断单 `budget_scope` 不得含「干预 / 一类证据 / 改页」。
- 人天按 `platforms_required` × 激活问法 × 允许窗，对照 `流程/07 预算和资源管理/工时标准.md`。

产出：`agent_pm/cases/{本案}/out/07_预算.md`。客户成交价不写进通用模板原件。
