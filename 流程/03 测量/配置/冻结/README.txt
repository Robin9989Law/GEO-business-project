开测前必须跑（写入本案冻结，不要当运行时回退源）：

python3 "流程/03 测量/工具/freeze_config.py" --date YYYY-MM-DD --case-id 本案

复制结果在 流程/03 测量/案件/{case_id}/冻结/YYYY-MM-DD/。
之后采集和出数加 --freeze-id YYYY-MM-DD --case-id 本案 --project-id 本案项目号。
没有本案冻结目录，脚本直接失败，不会回退共享配置。改问法 = 新冻结日，必须重打 baseline。
