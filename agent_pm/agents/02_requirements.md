---
stage: 02
purpose: 锁定项目章程与验收字段，apply 后停到 G1
entry_conditions:
  - G0 已过
  - sop_stage_intent 已锁
read_sources:
  - 合同/核心合同.md §1
  - 流程/02 需求文档/AGENT.md
  - 流程/02 需求文档/模板_项目章程.md
  - 流程/02 需求文档/模板_验收标准.md
  - 流程/02 需求文档/模板_需求规格.md
human_inputs:
  - 信息需求清单（02_need清单.md）
  - 合格竞品规则（02_竞品规则.md）
agent_writable_fields:
  - project_id
  - owner
  - sop_stage
  - primary_goal
  - primary_endpoint
  - causal_claim
  - control_design
  - success_rule_diagnosis
  - success_rule_sprint
  - success_rule_retain
  - treat_need_ids
  - holdout_need_ids
  - platforms_required
derived_fields: （无）
hard_rules:
  - sop_stage 不得宽于 sop_stage_intent
  - primary_endpoint 必须 p_mention
  - primary_goal 字面 = "在无品牌发现问上提高被正确提及的概率"
  - causal_claim 在 02 必须 = descriptive_until_isolation（did_isolated 仅 05 确认性 L1 后写入）
  - control_design = 监测组（不得称"反事实"）
  - 三套 success_rule_* 全写，且与 sop_stage 注册集一致
  - holdout_need_ids ∩ treat_need_ids = ∅
  - platforms_required 非空
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 02_章程
  - 02_验收标准
  - 02_需求规格
gate: G1
handoff_to:
  - 下一站 stage 07
  - 必须读字段: sop_stage, primary_goal, primary_endpoint, causal_claim, control_design, success_rule_*, treat_need_ids, holdout_need_ids, platforms_required
must_not:
  - primary_endpoint 写非 p_mention
  - control_design 用"反事实"称谓
  - 升 sop_stage（诊断不能升冲刺）
  - 缺一套 success_rule_*
---

# 02 需求 Agent

读取 01 已锁意向。锁定战略字段后停到 G1。

可写：`project_id` `sop_stage` `primary_goal` `primary_endpoint` `causal_claim` `control_design` `success_rule_diagnosis` `success_rule_sprint` `success_rule_retain` `treat_need_ids` `holdout_need_ids` `platforms_required`。

三套 `success_rule_*` 必须全部写，且与该 `sop_stage` 注册集一致：

- `success_rule_diagnosis` = 描述基线（默认）
- `success_rule_sprint` = 受控前后描述（默认）
- `success_rule_retain` = 不能下结论（默认）

`sop_stage` 不得宽于 `sop_stage_intent`（诊断不能升冲刺）。  
`primary_endpoint` 必须 `p_mention`。  
`causal_claim` 默认 `descriptive_until_isolation`。  
`holdout_need_ids` 与 `treat_need_ids` 不得相交。
