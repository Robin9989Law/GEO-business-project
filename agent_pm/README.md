# Agent 项目管理

核心机制：Agent **一步一步指导人**——这一步做什么、先做什么、要哪些材料、放到哪。人按说明书准备并在门上签字。

```bash
python3 agent_pm/run.py init CASE
python3 agent_pm/run.py guide CASE          # 给人看的分步说明书（默认）
python3 agent_pm/run.py next CASE --raw     # Agent 用的 JSON（含 guide）
python3 agent_pm/run.py apply CASE --json payload.json
python3 agent_pm/run.py decide CASE --gate G0 --verdict APPROVE --actor human
python3 agent_pm/run.py deposit CASE --src 路径 --stage 01
python3 agent_pm/run.py board CASE          # 中转待取 + 正式现行
python3 agent_pm/run.py drop CASE --src 路径 --from 操作员 --to 评分
python3 agent_pm/run.py profile CASE --member 负责人 --json profile.json
python3 agent_pm/run.py review CASE --member 负责人 --raw-id R0001 --json review.json
python3 agent_pm/run.py appeal CASE --review-id QR0001 --reason 文本
python3 agent_pm/run.py resolve-review CASE --review-id QR0001 --verdict UPHOLD --actor human --reason 文本
```

流程：教学引导 → 提交 → 质检 → 打回/复核/通过 → 起草 → 门检 → 人批准。`waiting` 仍是 agent/human/done；`activity` 是受约束的状态。讲解和软性打分由 Agent 做；硬规则、通过线、打回/复核权在引擎。每次 `review` 必须绑定 `raw_id` 或 `draft_id+checksum`。`appeal` / `resolve-review` 只能处理当前评审。有学习档案后，当前阶段没有 `PASS` / `OVERRIDE_SOFT` 不能 `apply`。Agent 永远不能 `APPROVE`。

编排先读 `agents/00_orchestrator.md`。当前阶段只读对应行走节点提示词（01→02→07→08→03→04→05→06→09），并始终读 `agents/10_files.md`。人只读 `agents/HUMAN.md`。G4 通过后还要走 09。材料归宿 `流程/10 项目文件/案件/CASE/`。

字段所有权来自 `合同/核心合同字段.csv`。引擎拒绝越权写、拒绝诊断升冲刺、拒绝诊断单排干预、拒绝人代 apply、拒绝 Agent 自己 APPROVE。
