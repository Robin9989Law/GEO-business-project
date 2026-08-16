# 人怎么被带着走

每次先问 Agent 或自己跑：

```bash
python3 agent_pm/run.py guide CASE
```

说明书会告诉你：**现在在哪一站、当前门是哪一个、先做什么、要哪些材料、放到哪、谁可以签字、做完再干什么。**

你只需要：
1. 开单时回答三个熟练度问题（项目管理 / GEO / 文件）。不会也没关系，Agent 会讲细，门槛不降。升熟练度只能人显式操作，系统不自动升级：

```bash
python3 agent_pm/run.py promote-profile CASE --member 你的代号 --axis pm_level --level 1
```

2. 按「先做」的顺序准备材料，放到写出的路径（inbox 或 `流程/10 项目文件/案件/CASE/原始/`；测量实物仍放 `流程/03 测量/`）。看 `中转/看板.md` 有没有给你的待取。
3. Agent 质检不合格会打回并告诉你改哪。硬规则不能申诉；软性打回可以申请复核。
4. 等 Agent 写完草稿后，审 `guide` 里的产出路径。过门前该阶段注册表里的必需正式件必须已在 `out/`。
5. 决策当前门。关键门（G1 / G3 / G4 / G8）必须两个不同成员、两个规定角色都签字，并写原因：

```bash
python3 agent_pm/run.py decide CASE --gate G1 --verdict APPROVE --actor human \
  --member owner_a --role 负责人 --decision-reason "章程字段已锁，禁售未破"

python3 agent_pm/run.py decide CASE --gate G1 --verdict APPROVE --actor human \
  --member owner_b --role GEO/验收专业复核 --decision-reason "验收三套规则与 sop_stage 一致"
```

单签门（G0 / G6 / G7 / G2 / G5）同样建议带 `--member --role --decision-reason`。角色对照见 `合同/关键门双角色表.md`。

CHANGE 必须附影响分析，不能只改口：

```bash
python3 agent_pm/run.py decide CASE --gate G5 --verdict CHANGE --actor human \
  --member owner_a --role 负责人 --rewind 04 --change-json change.json
```

`change.json` 至少含 `reason`、`affected_fields`、`affected_docs`、`invalidated`。

不要改 `state.json`，不要自己写四选一，不要代跑 `apply`。
只有人可以 `APPROVE`。G4 接收交付之后还要批 G8 才算全流程结束。
