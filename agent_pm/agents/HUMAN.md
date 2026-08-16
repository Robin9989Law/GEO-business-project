# 人怎么被带着走

每次先问 Agent 或自己跑：

```bash
python3 agent_pm/run.py guide CASE
```

说明书会告诉你：**现在做什么、先做什么、要哪些材料、放到哪、做完再干什么。**

你只需要：
1. 开单时回答三个熟练度问题（项目管理 / GEO / 文件）。不会也没关系，Agent 会讲细，门槛不降。
2. 按「先做」的顺序准备材料，放到写出的路径（inbox 或 `流程/10 项目文件/案件/CASE/原始/`；测量实物仍放 `流程/03 测量/`）。看 `中转/看板.md` 有没有给你的待取。
3. Agent 质检不合格会打回并告诉你改哪。硬规则不能申诉；软性打回可以申请复核。
4. 等 Agent 写完草稿后，审 `guide` 里的产出路径。
5. 决策当前门：

```bash
python3 agent_pm/run.py decide CASE --gate G0 --verdict APPROVE --actor human
```

不要改 `state.json`，不要自己写四选一，不要代跑 `apply`。
只有人可以 `APPROVE`。G4 接收交付之后还要批 G8 才算全流程结束。
