# 案件运行时

共享 `配置/` 与 `台账/samples.csv` 是模板/演示，不是第二单的工作区。

每案只写：

```text
流程/03 测量/案件/{case_id}/冻结/{freeze_id}/
流程/03 测量/案件/{case_id}/台账/samples.csv
流程/03 测量/案件/{case_id}/样本/
流程/03 测量/案件/{case_id}/清单/
流程/03 测量/案件/{case_id}/出数/
```

出数必须带 `--case-id` 与 `--project-id`，按 `project_id` / `freeze_id` / `config_checksum` 过滤。禁止把 A 案样本滚进 B 案报告。
