# 02 需求文档

过程组：启动。门：G1。

把 01 写成可执行合同并**锁定**战略字段。验收字段必须能直接抄进 `流程/03 测量/配置/project.csv`。

**读取：** 01 的 `{vertical}` `{city}` `{client_code}` 与意向产品线。  
**锁定：** `sop_stage` `primary_goal` `primary_endpoint` `causal_claim` `control_design` `treat_need_ids` `holdout_need_ids` `platforms_required` `success_rule_*`。  
**下游：** 07 按锁定范围估人天；08 按允许集锁口径；03 只灌入、不出新口径；04 只按锁定的 `sop_stage` 排窗。

| 文件 | 用途 |
|---|---|
| [模板_项目章程.md](模板_项目章程.md) | 为什么做、做到哪停 |
| [模板_需求规格.md](模板_需求规格.md) | 信息需求、平台、城市 |
| [模板_验收标准.md](模板_验收标准.md) | 三套 success_rule，禁止另写一套 |

出口：章程批准；`primary_endpoint=p_mention`；`causal_claim` 默认描述。
