# 资产库（跨项目复利）

项目账在 `出数/` 和客户报告里，回答「这一单 L1 有没有证据」。  
这里只收**脱敏后仍值钱**的东西：问法形态、品类谁被提到、各 App 引用哪些域、App–API 偏差、哪类干预曾经移动过分布。

不要把 `facts.csv`、截图、客户电话、`branded=1` 问法、fingerprint 放进来。

## 目录

| 路径 | 是什么 | 何时更新 |
|---|---|---|
| `词表池/needs.csv` | 无品牌信息需求 + 乱问形态 | 词表冻结后 |
| `面板/market_panel.csv` | 品类×城市×平台的提及结构（不标谁是甲方） | 每次 `asset_deposit.py` |
| `来源域/domains.csv` | 各 App 引用域名频次 | 同上 |
| `校准史/calibration_long.csv` | App–API gap 与版本 | 每次 calib |
| `干预复盘/plays.csv` | 脱敏后的干预类型与 L1 结论 | 每次 retest 人工一行 |
| `登记/deposits.csv` | 哪天存过什么 | 脚本自动 |

## 命令

```bash
python3 "流程/03 测量/工具/asset_deposit.py" --date 2026-08-18 --case-id 本案 --project-id 本案项目号
```

对照：`流程/03 测量/配置/project.csv`（这一单的目标）+ `asset_policy.csv`（能存什么）。
