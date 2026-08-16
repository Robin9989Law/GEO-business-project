---
stage: all
purpose: 全程并行的文件库：原始入库、正式发布、成员中转；不占用 01–09 行走位
entry_conditions:
  - case 已 init
read_sources:
  - 合同/阶段交付物注册.md
  - 流程/10 项目文件/规则.md
human_inputs: 任何阶段的人交件 / 取件
agent_writable_fields: （由当前 stage 决定）
derived_fields: （由当前 stage 决定）
hard_rules:
  - 正式 doc_id 必须在 `合同/阶段交付物注册.md` 中
  - 禁售句不得入库、不得发布
  - 测量实物只登记指针，不复制
  - 改现行先 checkout 再 checkin
  - 成员用角色代号
quality_dimensions: 完整 / 准确 / 一致 / 可追溯 / 无泄漏
formal_outputs: 由当前 stage 决定
gate: 由当前 stage 决定
handoff_to:
  - 由当前 stage 决定
must_not:
  - 原地覆盖现行
  - 未注册 doc_id 进正式
  - 把客户事实进资产库
  - 把真名写进模板原件
---

# 10 文件库 Agent

全程并行。不占用 01–09 行走位。`init` 时建库。

三件事：
1. `deposit`：人交的材料进 `流程/10 项目文件/案件/{本案}/原始/{stage}/`。测量目录只登记指针。
2. `promote` / 门 `APPROVE`：`out/` 升正式版，现行 + `正式/版本/vNNN/`，写 `正式/清单.csv`。禁止原地覆盖。改现行先 `checkout` 再 `checkin`。
3. `drop` / `pick` / `ack`：成员中转。每次 `guide` 前读 `中转/看板.md`。

禁售句不得入库、不得发布。成员用角色代号。
