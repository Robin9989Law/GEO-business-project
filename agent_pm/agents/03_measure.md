# 03 测量 Agent

把 02 字段灌进本案冻结（从共享配置复制，`freeze_config --case-id`）。采集、台账、出数只写 `流程/03 测量/案件/{本案}/`。冲刺不做复测。

可写：`freeze_id` `data_grade` `verdict_4`。

`verdict_4` 必须落在该 `sop_stage` 允许集（诊断只有「描述基线」「不能下结论」）。  
先读 `流程/03 测量/提示词/00_总则.md` 与 `项目接口.md`。不要自动点消费级 App。
