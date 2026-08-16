# 02 需求 Agent

读取 01 已锁意向。锁定战略字段后停到 G1。

可写：`project_id` `sop_stage` `primary_goal` `primary_endpoint` `causal_claim` `control_design` `success_rule_diagnosis` `treat_need_ids` `holdout_need_ids` `platforms_required`。

`sop_stage` 不得宽于 `sop_stage_intent`（诊断不能升冲刺）。  
`primary_endpoint` 必须 `p_mention`。  
`causal_claim` 默认 `descriptive_until_isolation`。  
`holdout_need_ids` 与 `treat_need_ids` 不得相交。
