---
stage: 06
purpose: 验收抄入 verdict_4（诊断/续约=03；冲刺=05 复测后），客户报告身份与冻结一致
entry_conditions:
  - G5 已过（冲刺）或 G3 已过（诊断/续约，无 G5）
  - 出数目录已生成
read_sources:
  - 合同/核心合同.md §1
  - 流程/06 交付物/AGENT.md
human_inputs:
  - 接收/拒收决定
agent_writable_fields:
  - delivery_manifest_checksum
  - freeze_match
  - delivery_accepted
derived_fields: （无）
hard_rules:
  - verdict_4 抄入来源正确（诊断/续约=03；冲刺=05 复测后）
  - verdict_4 仍落在 VERDICT_OK[sop_stage]
  - 出数目录必须齐：metrics_daily.csv + coverage.csv + evidence_manifest.json + 客户报告
  - 身份列 = 本案 freeze_id
  - 禁售句不得入客户报告
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 06_客户报告
  - 06_验收单
gate: G4
handoff_to:
  - 下一站 stage 09
  - 必须读字段: verdict_4, delivery_manifest_checksum, freeze_match, delivery_accepted
must_not:
  - 改 verdict_4
  - 把 API 当主表
  - 另写可见性表
  - 接收禁售报告
---

# 06 交付 Agent

验收单从 state 抄 `freeze_id` `verdict_4` `data_grade` `sop_stage`，路径 `流程/03 测量/案件/{本案}/出数/`。

`verdict_4` 抄入来源（**与 `合同/核心合同.md §1` 一致**）：

- 诊断/续约：从 03 抄入已锁 `verdict_4`。
- 冲刺：从 05 复测后已锁 `verdict_4` 抄入。

`verdict_4` 必须仍落在该 `sop_stage` 允许集。  
出数目录必须同时有 `metrics_daily.csv`、`coverage.csv`、`evidence_manifest.json` 和客户可见报告；身份列必须等于本案冻结。  
不要另写可见性表。停到 G4 等人接收。
