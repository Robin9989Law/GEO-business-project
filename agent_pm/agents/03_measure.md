---
stage: 03
purpose: 灌 02 字段进本案冻结，采集 App 冷问，出噪声/基线数。冲刺本步不做复测。
entry_conditions:
  - G1/G6/G7 已过
  - 02 战略字段已锁
read_sources:
  - 合同/核心合同.md §1
  - 流程/03 测量/AGENT.md
  - 流程/03 测量/项目接口.md
  - 流程/03 测量/提示词/00_总则.md
human_inputs:
  - 真机+干净号+定位
  - App 冷问 txt+截图
  - 第二人基线 Core 抽检
agent_writable_fields:
  - freeze_id
  - data_grade
  - baseline_verdict_4
derived_fields:
  - measure_isolated
  - config_checksum
hard_rules:
  - 未冻结不得采
  - 不自动点消费级 App
  - 诊断/续约 verdict_4：本步可写
  - 冲刺 verdict_4：05 复测后写（本步禁止）
  - baseline_verdict_4 ∈ {描述基线, 不能下结论}
  - verdict_4 ∈ VERDICT_OK[sop_stage]
  - 冻结与 02 字段一致（freeze_contract_errors）
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 03_冻结包
  - 03_环境登记
  - 03_出数报告
gate: G3
handoff_to:
  - 下一站 stage 04
  - 必须读字段: freeze_id, sop_stage, baseline_verdict_4
must_not:
  - 冲刺本步写最终 verdict_4
  - 写 L1/确认性因果
  - 把 API 当主表
  - 客户事实进 10 资产库
---

# 03 测量 Agent

把 02 字段灌进本案冻结（从共享配置复制，`freeze_config --case-id`）。采集、台账、出数只写 `流程/03 测量/案件/{本案}/`。冲刺在本步不做复测。

可写：`freeze_id` `data_grade` `baseline_verdict_4`。

最终 `verdict_4` 写入规则（**与 `合同/核心合同.md §1` 一致**）：

| `sop_stage` | 本步可写 | 最终 `verdict_4` 写入阶段 |
|---|---|---|
| 诊断 | `baseline_verdict_4` + `verdict_4` | 03（与 baseline 同步） |
| 续约 | `baseline_verdict_4` + `verdict_4` | 03 |
| 冲刺 | `baseline_verdict_4` | **05 复测后**（本步禁止写最终 `verdict_4`） |

`verdict_4` 必须落在该 `sop_stage` 允许集（诊断只有「描述基线」「不能下结论」）。  
`baseline_verdict_4` 只允许「描述基线」「不能下结论」。  
先读 `流程/03 测量/提示词/00_总则.md` 与 `项目接口.md`。不要自动点消费级 App。
