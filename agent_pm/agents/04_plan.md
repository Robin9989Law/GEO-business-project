---
stage: 04
purpose: 只排 02+03 允许的窗；plan_hours ≤ budget_hours；不超 sop_stage 允许集
entry_conditions:
  - G3 已过
  - freeze_id, sop_stage, budget_hours 已有
read_sources:
  - 合同/核心合同.md §1
  - 流程/04 项目计划/AGENT.md
human_inputs:
  - WBS/进度草稿
  - RACI、风险/依赖
agent_writable_fields:
  - plan_hours
derived_fields: （无）
hard_rules:
  - windows ⊆ STAGE_WINDOWS[sop_stage]
  - plan_hours > 0
  - plan_hours ≤ budget_hours
  - 诊断窗 ⊆ {day0, noise, baseline}
  - 冲刺窗 ⊆ {day0, noise, baseline, intervention, wait, retest}
  - 续约窗 ⊆ {day0, weekly, calib}
  - 复测窗归属 05（不是 03 基线）
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 04_进度
gate: G2
handoff_to:
  - 下一站 stage 05
  - 必须读字段: plan_hours, windows, sop_stage
must_not:
  - 把冲刺工作写进诊断单
  - 排超出 sop_stage 的窗
  - plan_hours > budget_hours
---

# 04 计划 Agent

只排 02+03 允许的窗。apply 时带 `windows` 列表。

诊断只许 `noise` `baseline`。  
冲刺可加 `retest` `intervention`。  
续约只许 `weekly` `calib`。

可写字段以 `next` 为准。不要把冲刺工作写进诊断单。
