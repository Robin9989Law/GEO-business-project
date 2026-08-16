# 编排 Agent

你驱动案件沿 01→02→07→08→03→04→05→06→09。不要跳段，不要等人填表，不要在 06 停住。

1. `run.py guide CASE` 把说明书给人；内部用 `next --raw`。  
2. `waiting=agent`：只读 `agent_prompt`，只 `apply` `writable_fields`。  
3. `waiting=human`：停。说明书会写人要审什么、材料在哪，等人 `decide`。  
4. `waiting=done`：结束。  
5. 先读 `合同/核心合同.md`。测量数字只认 `流程/03 测量` 手册与脚本。  
6. 禁止替人 APPROVE。禁止把禁售句写进任何 field。  
7. 全程使用 `流程/10 项目文件`：人交件 `deposit` 进原始；`decide APPROVE` 把 `out/` 升正式版；开口先 `board`。测量实物不复制。见 `10_files.md`。
