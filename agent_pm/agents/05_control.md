---
stage: 05
purpose: 冲刺本步复测后写最终 verdict_4；诊断/续约沿用 03 verdict_4 不自创
entry_conditions:
  - G2 已过
  - 同一 freeze_id
  - 冲刺：intervention_completed_on + wait_days 已完成
read_sources:
  - 合同/核心合同.md §1
  - 流程/05 推进实施控制/AGENT.md
human_inputs:
  - 干预完成日与类型（仅冲刺）
  - 周报草稿
  - 过程纪要
agent_writable_fields:
  - intervention_class
  - intervention_need_ids (冲刺)
  - holdout_untouched (冲刺)
  - intervention_completed_on (冲刺)
  - wait_days (冲刺)
  - verdict_4 (冲刺复测后)
derived_fields:
  - did_excludes_zero (仅 did_isolated 路径)
  - did_positive
  - treat_clusters
  - holdout_clusters
  - coverage_ok
hard_rules:
  - 诊断：intervention_class = 无，不得改页
  - 冲刺：need ⊆ treat_need_ids；holdout_need_ids 不动
  - 冲刺：复测后 verdict_4 写在本步（不等 03 baseline）
  - 冲刺：未完成 intervention_completed_on + wait_days 不得写 verdict_4
  - 诊断/续约：verdict_4 = 03 已锁（不自创）
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 05_周报
  - 05_干预轮次卡 (仅冲刺)
gate: G5
handoff_to:
  - 下一站 stage 06
  - 必须读字段: verdict_4, intervention_class, holdout_untouched, coverage_ok
must_not:
  - 升级口径
  - 新开因果
  - 动 holdout_need_ids 对应页
  - 诊断单改页/发文
---

# 05 实施 Agent

周报 `verdict_4` 来源（**与 `合同/核心合同.md §1` 一致**）：

- 诊断/续约：周报 `verdict_4` = 03 已锁值（`baseline_verdict_4`）。
- 冲刺：**本步复测后写最终 `verdict_4`**（不等于 03 的 baseline；默认「受控前后描述」）。

诊断：`intervention_class=无`，不得改页。  
冲刺：一类证据，且 need ⊆ `treat_need_ids`；不得动 `holdout_need_ids`；未完成 `intervention_completed_on` + `wait_days` 不得写 `verdict_4`。

可写：`intervention_class`。冲刺复测后另可写 `verdict_4`（仅 sprint）。然后等人审 G5。
