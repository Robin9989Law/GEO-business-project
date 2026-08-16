# 工程（实现层）

状态机和检查器。不改测量口径。

| 路径 | 用途 |
|---|---|
| [`../agent_pm/`](../agent_pm/README.md) | 开单、guide、apply、decide、文件库 |
| [check_pm_system.py](check_pm_system.py) | 模板齐全且无客户泄漏 |
| [test_pm_system.py](test_pm_system.py) | 驱动上一检查 |
| `../agent_pm/test_agent_pm.py` | 全流程状态机 |
| `../agent_pm/test_files.py` | 10 原始 / 正式 / 中转 |
| `../流程/03 测量/工具/test_measure.py` | 出数与覆盖 |

从仓库根：

```bash
python3 check_pm_system.py
python3 工程/test_pm_system.py
python3 agent_pm/test_agent_pm.py
python3 agent_pm/test_files.py
python3 "流程/03 测量/工具/test_measure.py"
```
