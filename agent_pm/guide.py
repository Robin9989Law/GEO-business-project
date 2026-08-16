#!/usr/bin/env python3
"""按当前案件状态生成给人看的分步指导。全流程 01→09。"""

from __future__ import annotations

import engine as _eng

GATE_AFTER = _eng.GATE_AFTER
STAGE_WINDOWS = _eng.STAGE_WINDOWS
VERDICT_OK = _eng.VERDICT_OK
STAGE_FOLDER = _eng.STAGE_FOLDER

# 每阶段：先做什么 → 人做什么 → 材料放哪 → 然后做什么
PLAYBOOK = {
    "01": {
        "title": "洽谈收口",
        "do_first": [
            "先听客户原话：他们想在 AI 里被怎么问到",
            "先读 流程/01 客户初次洽谈/禁售清单.md，再开口报价",
        ],
        "human_does": [
            "提供品类口头说法、目标城市、客户代号（不要全称）",
            "选定意向产品线：诊断 / 冲刺 / 续约（只能选一条）",
            "若客户要「保证推荐/报名增长」：停在本步，不要立项",
        ],
        "materials": [
            {"item": "客户原话（怎么被发现）", "put_at": "agent_pm/cases/{case}/inbox/01_客户原话.md", "why": "01 Agent 抽 vertical/city/意向"},
            {"item": "禁售已读回执", "put_at": "agent_pm/cases/{case}/inbox/01_禁售已读.txt", "why": "G0 才能批"},
        ],
        "then": "Agent 写入商机字段后，你审 G0：APPROVE 才进 02",
    },
    "02": {
        "title": "锁定需求与验收",
        "do_first": [
            "必须已过 G0",
            "意向 sop_stage 只能收窄不能加宽（诊断不能升冲刺）",
        ],
        "human_does": [
            "确认处理组信息需求 treat_need_ids（每条至少两种问法形态）",
            "确认监测组 holdout_need_ids（同品类同城，本轮不优化）",
            "确认必测平台 platforms_required（默认 P0）",
            "审章程：主终点只能是无品牌问上的 p_mention",
        ],
        "materials": [
            {"item": "信息需求清单", "put_at": "agent_pm/cases/{case}/inbox/02_need清单.md", "why": "灌 queries 的 treat/holdout"},
            {"item": "合格竞品怎么定义", "put_at": "agent_pm/cases/{case}/inbox/02_竞品规则.md", "why": "aliases 里 competitor"},
        ],
        "then": "Agent 锁定字段后，你审 G1。通过后进 07 预算，还不到 03 采集",
    },
    "07": {
        "title": "预算与人天（测量前锁定）",
        "do_first": [
            "必须已过 G1，sop_stage / 平台 / need 已锁",
            "先按 platforms_required × 激活问法 × 本产品线允许的窗估人天，再谈价",
            "诊断单不得把一类证据 / 改页写进必做行",
        ],
        "human_does": [
            "提供可用人天、单价口径（不要把客户成交价写进通用模板）",
            "确认报价排除确认性 L1：quote_excludes_l1=是",
            "诊断：预算范围只能覆盖冻结、噪声、基线、抽检、收尾",
        ],
        "materials": [
            {"item": "人手与单价约束", "put_at": "agent_pm/cases/{case}/inbox/07_人手.md", "why": "填预算表人天"},
            {"item": "预算表（本案副本）", "put_at": "agent_pm/cases/{case}/out/07_预算.md", "why": "G6 审的就是这个；对照 流程/07 预算和资源管理/预算表.csv 与 工时标准.md"},
        ],
        "then": "你审 G6。通过后进 08 沟通立项，再才进 03 测量",
    },
    "08": {
        "title": "沟通立项（测量前锁定口径）",
        "do_first": [
            "必须已过 G6",
            "先登记谁收什么级别的结论，再允许对外说话",
            "对外口径不得宽于当前 sop_stage 允许的四选一",
        ],
        "human_does": [
            "点名客户决策人、对接人、内部负责人（可用代号，不要写进通用模板原件）",
            "确认决策人只收四选一，不把 API 附表当主表",
            "确认沟通 comms_bound 写明「不得宽于四选一」",
        ],
        "materials": [
            {"item": "干系人名单", "put_at": "agent_pm/cases/{case}/inbox/08_干系人.md", "why": "抄进 流程/08 沟通/干系人登记.csv 本案行"},
            {"item": "沟通矩阵本案稿", "put_at": "agent_pm/cases/{case}/out/08_沟通矩阵.md", "why": "G7；对照 流程/08 沟通/沟通矩阵.md"},
        ],
        "then": "你审 G7。通过后才打开 03 测量开始冻结和采集",
    },
    "03": {
        "title": "测量：冻结 → 人采 App → 出数",
        "do_first": [
            "必须已过 G1、G6、G7：需求、预算、沟通都已锁",
            "从共享配置复制到本案后冻结：freeze_config --case-id 本案；未冻结不准采",
            "先采噪声底，再谈涨跌。冲刺本步不做复测",
        ],
        "human_does": [
            "准备真机、干净号、定位切到合同里的城市",
            "按当日清单做 App 冷问：新建对话、原话一句、截图+全文",
            "基线 Core 必须第二人抽检",
            "不要自动点消费级 App",
        ],
        "materials": [
            {"item": "本案冻结（复制源是共享配置）", "put_at": "流程/03 测量/案件/{case}/冻结/{freeze}/", "why": "G3 对合同绑定"},
            {"item": "机型与版本", "put_at": "流程/03 测量/案件/{case}/环境登记.txt", "why": "产品模式当天一种"},
            {"item": "App 冷问 txt+截图", "put_at": "流程/03 测量/案件/{case}/样本/{date}/{channel}/{query_id}_r{n}.txt|.png", "why": "金标准样本"},
            {"item": "评分", "put_at": "流程/03 测量/案件/{case}/台账/samples.csv", "why": "出数分母"},
            {"item": "出数", "put_at": "流程/03 测量/案件/{case}/出数/", "why": "rollup --case-id --project-id"},
        ],
        "then": "Agent 跑冻结、噪声、基线出数；你审 G3。冲刺不要在本步复测或写确认性 L1",
    },
    "04": {
        "title": "计划只排测量允许的窗，且不超 07 预算",
        "do_first": [
            "必须已有 freeze_id、sop_stage、07 的 budget_hours",
            "先看 03 允许的任务，再排人天；人天不得超出 G6 已批预算",
        ],
        "human_does": [
            "核对进度里没有超出 sop_stage 的窗（诊断不得有干预窗）",
            "按 platforms_required × 激活问法看人天是否够，且 ≤ budget_hours",
        ],
        "materials": [
            {"item": "WBS/进度草稿", "put_at": "agent_pm/cases/{case}/out/04_进度.md", "why": "G2 审的就是这个"},
        ],
        "then": "你审 G2。通过后才允许 05 动手",
    },
    "05": {
        "title": "实施控制",
        "do_first": [
            "必须同一 freeze_id",
            "诊断：整步无改页；冲刺：一轮一类证据",
            "对外说话走 08 已锁矩阵，口径不得宽于 03 四选一",
        ],
        "human_does": [
            "诊断：不要改客户页、不要发新文",
            "冲刺：只改 treat_need_ids 对应页面，监测组不改",
            "周报四选一必须与 03 的 verdict_4 相同，不要自己升级",
        ],
        "materials": [
            {"item": "干预完成日与类型（仅冲刺）", "put_at": "流程/03 测量/案件/{case}/冻结/{freeze}/intervention_ledger.csv", "why": "复测对得上日期"},
            {"item": "周报审阅", "put_at": "agent_pm/cases/{case}/out/05_周报.md", "why": "G5"},
            {"item": "过程纪要", "put_at": "agent_pm/cases/{case}/out/08_纪要.md", "why": "对照 流程/08 沟通/模板_会议纪要.md"},
        ],
        "then": "诊断 G5 自动不适用；冲刺复测后写最终四选一再审 G5",
    },
    "06": {
        "title": "交付验收",
        "do_first": [
            "先打开 流程/03 测量/案件/{case}/出数/ 报告，不要另做可见性表",
            "核对 verdict_4、freeze_id、覆盖与 02/03/05 一致",
        ],
        "human_does": [
            "按 sop_stage 允许集接收或拒收",
            "诊断只能收「描述基线」或「不能下结论」",
            "出现禁售句则拒收",
        ],
        "materials": [
            {"item": "出数报告", "put_at": "流程/03 测量/案件/{case}/出数/metrics_daily.csv", "why": "唯一可见性交付"},
            {"item": "验收决定", "put_at": "agent_pm/cases/{case}/out/06_验收单.md", "why": "G4"},
        ],
        "then": "G4 APPROVE 后进 09 收尾，案件还没结束",
    },
    "09": {
        "title": "收尾：结项、教训、资产移交",
        "do_first": [
            "必须已过 G4，验收四选一已锁",
            "先跑资产沉淀，再写结项；结项不得重开 L1",
            "检查库里没有客户事实、截图、电话、全称",
        ],
        "human_does": [
            "确认 asset_deposit 已跑、deposits.csv 有本日",
            "确认结项报告的实际交付 = 06 已收的 verdict_4",
            "经验教训只写可迁移结构，不写客户故事",
            "close_no_reopen_l1=是，close_assets_ok=是",
        ],
        "materials": [
            {"item": "结项报告", "put_at": "agent_pm/cases/{case}/out/09_结项报告.md", "why": "对照 流程/09 收尾/模板_结项报告.md；G8"},
            {"item": "经验教训", "put_at": "agent_pm/cases/{case}/out/09_经验教训.md", "why": "对照 流程/09 收尾/模板_经验教训.md"},
            {"item": "资产移交检查", "put_at": "agent_pm/cases/{case}/out/09_资产移交.md", "why": "对照 流程/09 收尾/模板_资产移交.md"},
        ],
        "then": "你审 G8。APPROVE 后案件 done",
    },
}


def build_guide(state: dict) -> dict:
    case = state.get("case_id") or "CASE"
    stage = state.get("stage") or "01"
    waiting = state.get("waiting") or "agent"
    fields = state.get("fields") or {}
    sop = fields.get("sop_stage") or fields.get("sop_stage_intent") or "（未锁）"
    book = PLAYBOOK[stage] if stage in PLAYBOOK else PLAYBOOK["01"]
    mats = []
    for m in book["materials"]:
        mats.append({k: v.replace("{case}", case) for k, v in m.items()})
    if waiting == "done":
        now = "全流程已结束。你只做最终抽查：出数报告有没有禁售句、四选一有没有超 sop_stage、资产库有没有客户事实。"
        role = "human_review"
    elif waiting == "human":
        gate = GATE_AFTER.get(stage, "")
        now = f"材料已齐或草稿已写。请你审核后决策 {gate}：APPROVE / REJECT / CHANGE。"
        role = "human_decide"
    else:
        now = f"现在轮到 Agent 写 {stage} 字段。请你按「先做」准备材料，放到指定目录，不要自己改 state.json。"
        role = "human_prepare"
    allowed = sorted(STAGE_WINDOWS.get(sop, ())) if sop in STAGE_WINDOWS else []
    verdicts = sorted(VERDICT_OK.get(sop, ())) if sop in VERDICT_OK else []
    import teaching as _teach

    proc = _teach.process_guide(state)
    return {
        "case_id": case,
        "stage": stage,
        "folder": STAGE_FOLDER.get(stage, stage),
        "title": book["title"],
        "sop_stage": sop,
        "waiting": waiting,
        "activity": proc["activity"],
        "mode": proc["mode"],
        "teach_focus": proc["teach_focus"],
        "process": proc,
        "role_now": role,
        "now": now,
        "do_first": list(book["do_first"]),
        "human_does": list(book["human_does"]),
        "materials": mats,
        "then": book["then"],
        "allowed_windows": allowed,
        "allowed_verdicts": verdicts,
        "freeze_id": fields.get("freeze_id") or "（尚未冻结）",
        "budget_hours": fields.get("budget_hours") or "（07 尚未锁定）",
        "put_inbox": f"agent_pm/cases/{case}/inbox/",
        "put_out": f"agent_pm/cases/{case}/out/",
        "put_raw": f"流程/10 项目文件/案件/{case}/原始/{stage}/",
        "put_formal": f"流程/10 项目文件/案件/{case}/正式/现行/",
        "put_board": f"流程/10 项目文件/案件/{case}/中转/看板.md",
    }


def format_guide(g: dict) -> str:
    lines = [
        f"# 下一步（{g['case_id']}）",
        f"阶段：{g['stage']} {g.get('folder', '')} {g['title']}　产品线：{g['sop_stage']}　冻结：{g['freeze_id']}",
        f"现在：{g['now']}",
        f"活动：{g.get('activity') or ''}　教学深度：{g.get('mode') or 'standard'}（讲解由 Agent 做）　本步重点：{g.get('teach_focus') or ''}",
        "",
        "## 先做（顺序不要倒）",
    ]
    for i, x in enumerate(g["do_first"], 1):
        lines.append(f"{i}. {x}")
    lines += ["", "## 需要你做"]
    for i, x in enumerate(g["human_does"], 1):
        lines.append(f"{i}. {x}")
    lines += ["", "## 材料放哪"]
    for m in g["materials"]:
        lines.append(f"- {m['item']} → `{m['put_at']}` （{m['why']}）")
    lines += [
        f"- 本步inbox（先丢这里，Agent 必须转入原始库）：`{g['put_inbox']}`",
        f"- 原始资料归宿：`{g.get('put_raw', '')}`",
        f"- 正式现行：`{g.get('put_formal', '')}`",
        f"- 成员中转看板：`{g.get('put_board', '')}`",
        f"- Agent产出：`{g['put_out']}`（过门后发布进正式库）",
        "",
        f"## 然后：{g['then']}",
    ]
    proc = g.get("process") or {}
    if proc.get("ask_onboarding"):
        lines += ["", "## 开单先问（答完再交材料）"]
        for q in proc.get("onboarding_questions") or []:
            lines.append(f"- {q}")
    if proc.get("slots"):
        lines += ["", "## 本轮流程槽（讲解由 Agent 填，不要让人自己翻 SOP）"]
        for i, slot in enumerate(proc["slots"], 1):
            lines.append(f"{i}. {slot}")
        lines.append(f"标准流程：{proc.get('flow') or ''}")
    if g.get("budget_hours"):
        lines.append(f"已锁人天：{g['budget_hours']}")
    if g["allowed_windows"]:
        lines.append(f"本产品线允许的窗：{', '.join(g['allowed_windows'])}")
    if g["allowed_verdicts"]:
        lines.append(f"本产品线允许的四选一：{', '.join(g['allowed_verdicts'])}")
    return "\n".join(lines) + "\n"
