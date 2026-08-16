---
stage: 09
purpose: 结项、教训、资产移交；不得重开 L1；verdict_4 只回声 06
entry_conditions:
  - G4 已过
  - 06 verdict_4 已锁
read_sources:
  - 合同/核心合同.md §1
  - 流程/09 收尾/AGENT.md
  - 流程/10 项目文件/规则.md
human_inputs:
  - 资产移交确认
  - 教训草稿
agent_writable_fields:
  - close_assets_ok
  - close_no_reopen_l1
  - close_manifest_ok
  - close_board_empty
  - close_archive_ok
derived_fields: （无）
hard_rules:
  - close_assets_ok = 是（人已抽查 + deposits.csv 已跑 + 冲刺 plays.csv 一行）
  - close_no_reopen_l1 = 是（结项实际交付 = 06 verdict_4）
  - close_manifest_ok = 是（正式清单与 G0–G4 对应）
  - close_board_empty = 是（10 中转无未取）
  - close_archive_ok = 是（无锁 + 脱敏 + 移交件齐）
  - verdict_4 只许回声 06 已抄入值
  - 教训只写可迁移结构
  - 资产库无客户事实
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 09_结项报告
  - 09_经验教训
  - 09_资产移交
gate: G8
handoff_to: （none，G8 之后 done）
must_not:
  - 重开 L1
  - 把客户故事写进教训
  - 资产库留客户事实
  - 06 抄入的 verdict_4 改了
---

# 09 收尾 Agent

G4 之后关项。apply 后停到 G8。G4 通过不是结案。

可写：`close_assets_ok` `close_no_reopen_l1`。`verdict_4` 只许回声 **06 已抄入的最终值**（诊断/续约来自 03；冲刺来自 05 复测后）。

必须：
- `close_assets_ok=是`：人确认已抽查；引擎另查 `deposits.csv` 本案 `project_anon`、无泄漏、冲刺 `plays.csv`。
- `close_no_reopen_l1=是`：结项实际交付 = 06 已收四选一。
- 正式清单不得为空，且对上已批的 G0–G4。
- 教训只写可迁移结构。

产出（G8 批准前必须已在 `out/`）：`out/09_结项报告.md` `out/09_经验教训.md` `out/09_资产移交.md`。
