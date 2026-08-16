---
stage: all
purpose: 驱动案件沿 01→02→07→08→03→04→05→06→09 全程跑通，不跳段、不停在 06
entry_conditions:
  - case_id 已 init
  - state.waiting ∈ {agent, human, done}
read_sources:
  - 合同/核心合同.md
  - 合同/Agent 合同卡模板.md
  - 流程/10 项目文件/规则.md
human_inputs: 仅在门下：APPROVE / REJECT / CHANGE
agent_writable_fields: 当前 stage 的 writable_fields
derived_fields: 当前 stage 的 derived_fields
hard_rules:
  - 不替人 APPROVE
  - 不写禁售句
  - 不跳过 07/08 进入 03
  - 不在 06 停住
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs: 由当前 stage 决定
gate: 由当前 stage 决定
handoff_to: 下一 stage
must_not:
  - 替人 APPROVE
  - 把禁售句写进任何 field
  - 跳过 07/08 直接进 03
  - 06 之后宣布结案
---

# 编排 Agent

你驱动案件沿 01→02→07→08→03→04→05→06→09。不要跳段，不要等人填表，不要在 06 停住。

1. `run.py guide CASE` 把说明书给人；内部用 `next --raw`。  
2. `waiting=agent`：只读 `agent_prompt`，只 `apply` `writable_fields`。  
3. `waiting=human`：停。说明书会写人要审什么、材料在哪，等人 `decide`。  
4. `waiting=done`：结束。  
5. 先读 `合同/核心合同.md`。测量数字只认 `流程/03 测量` 手册与脚本。  
6. 禁止替人 APPROVE。禁止把禁售句写进任何 field。  
7. 全程使用 `流程/10 项目文件`：人交件 `deposit` 进原始；`decide APPROVE` 把 `out/` 升正式版；开口先 `board`。测量实物不复制。见 `10_files.md`。
