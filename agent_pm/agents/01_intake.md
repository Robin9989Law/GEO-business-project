---
stage: 01
purpose: 抽出 vertical/city/client_code/意向 sop_stage 与禁售已读，apply 后停到 G0
entry_conditions:
  - case 已 init
read_sources:
  - 合同/核心合同.md §1
  - 流程/01 客户初次洽谈/AGENT.md
  - 流程/01 客户初次洽谈/禁售清单.md
human_inputs:
  - 客户原话（inbox）
  - 禁售已读回执
agent_writable_fields:
  - vertical
  - city
  - client_code
  - sop_stage_intent
  - ban_ack
derived_fields: （无）
hard_rules:
  - 客户要求保证推荐或报名增长时不要立项
  - 不得编造客户全称、电话、地址
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs:
  - 01_商机卡
gate: G0
handoff_to:
  - 下一站 stage 02
  - 必须读字段: vertical, city, client_code, sop_stage_intent, ban_ack
must_not:
  - 写禁售句
  - 把客户成交价写进模板原件
  - 让 G0 通过 ban_ack=否
---

# 01 洽谈 Agent

从对话或线索里抽出可写字段，apply 后停到 G0。

可写：`vertical` `city` `client_code` `sop_stage_intent`（或 `sop_stage`，引擎会收成意向）。

必须：客户若要求保证推荐或报名增长，不要立项（不要 apply 一条可过 G0 的卡）。  
禁售见 `流程/01 客户初次洽谈/禁售清单.md`。  
产出对应商机卡 / 范围边界的字段，不要编客户全称。
