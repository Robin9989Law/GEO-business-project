#!/usr/bin/env python3
"""检查通用项目管理模板是否齐全，且未被写成某一客户的档案。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "AGENTS.md",
    "check_pm_system.py",
    ".gitignore",
    "流程/01 客户初次洽谈/AGENT.md",
    "流程/02 需求文档/AGENT.md",
    "流程/03 测量/AGENT.md",
    "流程/04 项目计划/AGENT.md",
    "流程/05 推进实施控制/AGENT.md",
    "流程/06 交付物/AGENT.md",
    "合同/项目流程SOP.md",
    "合同/核心合同.md",
    "合同/核心合同字段.csv",
    "合同/阶段教学与质检.json",
    "合同/案件合同卡.md",
    "合同/模板使用说明.md",
    "合同/README.md",
    "工程/README.md",
    "研究/README.md",
    "流程/README.md",
    "研究/文献精读_测量方案补强_V1.md",
    "流程/03 测量/文献.md",
    "流程/03 测量/案件/README.md",
    "流程/01 客户初次洽谈/README.md",
    "流程/01 客户初次洽谈/模板_商机卡.md",
    "流程/01 客户初次洽谈/模板_范围边界.md",
    "流程/01 客户初次洽谈/禁售清单.md",
    "流程/02 需求文档/README.md",
    "流程/02 需求文档/模板_项目章程.md",
    "流程/02 需求文档/模板_需求规格.md",
    "流程/02 需求文档/模板_验收标准.md",
    "流程/03 测量/项目接口.md",
    "流程/04 项目计划/README.md",
    "流程/04 项目计划/模板_WBS.md",
    "流程/04 项目计划/模板_进度基线.md",
    "流程/04 项目计划/模板_RACI.md",
    "流程/04 项目计划/风险登记.csv",
    "流程/04 项目计划/假设与约束.md",
    "流程/05 推进实施控制/README.md",
    "流程/05 推进实施控制/模板_周报.md",
    "流程/05 推进实施控制/模板_变更申请.md",
    "流程/05 推进实施控制/模板_干预轮次卡.md",
    "流程/05 推进实施控制/问题日志.csv",
    "流程/06 交付物/README.md",
    "流程/06 交付物/交付物注册表.csv",
    "流程/06 交付物/模板_验收单.md",
    "流程/07 预算和资源管理/README.md",
    "流程/07 预算和资源管理/预算表.csv",
    "流程/07 预算和资源管理/工时标准.md",
    "流程/08 沟通/README.md",
    "流程/08 沟通/干系人登记.csv",
    "流程/08 沟通/沟通矩阵.md",
    "流程/08 沟通/模板_会议纪要.md",
    "流程/09 收尾/README.md",
    "流程/09 收尾/模板_结项报告.md",
    "流程/09 收尾/模板_经验教训.md",
    "流程/09 收尾/模板_资产移交.md",
    "agent_pm/README.md",
    "工程/check_pm_system.py",
    "工程/test_pm_system.py",
    "agent_pm/engine.py",
    "agent_pm/guide.py",
    "agent_pm/teaching.py",
    "agent_pm/review.py",
    "agent_pm/run.py",
    "agent_pm/test_agent_pm.py",
    "agent_pm/test_teaching.py",
    "流程/07 预算和资源管理/AGENT.md",
    "流程/08 沟通/AGENT.md",
    "流程/09 收尾/AGENT.md",
    "agent_pm/agents/00_orchestrator.md",
    "agent_pm/agents/01_intake.md",
    "agent_pm/agents/02_requirements.md",
    "agent_pm/agents/03_measure.md",
    "agent_pm/agents/04_plan.md",
    "agent_pm/agents/05_control.md",
    "agent_pm/agents/06_deliver.md",
    "agent_pm/agents/07_budget.md",
    "agent_pm/agents/08_comms.md",
    "agent_pm/agents/09_close.md",
    "agent_pm/agents/10_files.md",
    "agent_pm/agents/HUMAN.md",
    "agent_pm/files.py",
    "agent_pm/test_files.py",
    "流程/10 项目文件/AGENT.md",
    "流程/10 项目文件/README.md",
    "流程/10 项目文件/规则.md",
    "流程/10 项目文件/模板/入库单.md",
    "流程/10 项目文件/模板/正式发布单.md",
    "流程/10 项目文件/模板/中转单.md",
    "流程/10 项目文件/模板/清单.csv",
    "流程/10 项目文件/模板/原始登记.csv",
    "流程/10 项目文件/模板/往来.csv",
    "流程/10 项目文件/模板/成员登记.csv",
    "流程/10 项目文件/模板/看板.md",
    "流程/10 项目文件/案件/README.md",
]

GENERIC_ROOTS = [
    ROOT / "AGENTS.md",
    ROOT / "合同",
    ROOT / "工程" / "README.md",
    ROOT / "流程" / "README.md",
    ROOT / "研究" / "README.md",
    ROOT / "研究" / "文献精读_测量方案补强_V1.md",
    ROOT / "流程/03 测量" / "文献.md",
    ROOT / "流程/01 客户初次洽谈",
    ROOT / "流程/02 需求文档",
    ROOT / "流程/04 项目计划",
    ROOT / "流程/05 推进实施控制",
    ROOT / "流程/06 交付物",
    ROOT / "流程/07 预算和资源管理",
    ROOT / "流程/08 沟通",
    ROOT / "流程/09 收尾",
    ROOT / "流程/03 测量" / "项目接口.md",
    ROOT / "流程/03 测量" / "AGENT.md",
    ROOT / "agent_pm" / "README.md",
    ROOT / "agent_pm" / "agents",
    ROOT / "流程/10 项目文件" / "AGENT.md",
    ROOT / "流程/10 项目文件" / "README.md",
    ROOT / "流程/10 项目文件" / "规则.md",
    ROOT / "流程/10 项目文件" / "模板",
    ROOT / "流程/10 项目文件" / "案件" / "README.md",
]

BANNED = ("叉车", "铲车", "示例培训", "质安", "竞品甲", "示例市")

GATES = (
    ("README.md", "合同/"),
    ("README.md", "工程/"),
    ("README.md", "研究/"),
    ("README.md", "流程/"),
    ("流程/README.md", "01→02→07→08→03→04→05→06→09"),
    ("AGENTS.md", "第一句话必须这样说"),
    ("AGENTS.md", "材料放到本仓库的哪条路径"),
    ("流程/01 客户初次洽谈/AGENT.md", "G0"),
    ("流程/03 测量/AGENT.md", "流程/03 测量/案件/"),
    ("流程/03 测量/AGENT.md", "baseline_verdict_4"),
    ("流程/05 推进实施控制/AGENT.md", "复测后才写"),
    ("流程/10 项目文件/规则.md", "隔离"),
    ("流程/06 交付物/AGENT.md", "G4"),
    ("合同/项目流程SOP.md", "descriptive_until_isolation"),
    ("合同/项目流程SOP.md", "{vertical}"),
    ("合同/项目流程SOP.md", "01→02→07→08→03→04→05→06→09"),
    ("合同/核心合同.md", "treat_need_ids"),
    ("合同/核心合同.md", "verdict_4"),
    ("合同/核心合同.md", "01 洽谈 → 02 需求 → 07 预算 → 08 沟通 → 03 测量"),
    ("AGENTS.md", "流程/07 预算和资源管理/AGENT.md"),
    ("AGENTS.md", "流程/09 收尾/AGENT.md"),
    ("流程/07 预算和资源管理/AGENT.md", "G6"),
    ("流程/07 预算和资源管理/AGENT.md", "quote_excludes_l1"),
    ("流程/08 沟通/AGENT.md", "G7"),
    ("流程/08 沟通/AGENT.md", "comms_bound"),
    ("流程/09 收尾/AGENT.md", "G8"),
    ("流程/09 收尾/AGENT.md", "close_no_reopen_l1"),
    ("流程/10 项目文件/AGENT.md", "原始"),
    ("流程/10 项目文件/AGENT.md", "正式/现行"),
    ("流程/10 项目文件/AGENT.md", "中转/看板.md"),
    ("流程/10 项目文件/规则.md", "清单.csv"),
    ("AGENTS.md", "流程/10 项目文件/AGENT.md"),
    ("合同/核心合同.md", "文件总线"),
    ("agent_pm/files.py", "promote_formal"),
    ("流程/01 客户初次洽谈/禁售清单.md", "确认性 L1"),
    ("流程/01 客户初次洽谈/模板_商机卡.md", "sop_stage"),
    ("流程/02 需求文档/模板_验收标准.md", "success_rule_diagnosis"),
    ("流程/02 需求文档/模板_验收标准.md", "causal_claim"),
    ("流程/02 需求文档/模板_需求规格.md", "treat_need_ids"),
    ("流程/03 测量/项目接口.md", "freeze_id"),
    ("流程/03 测量/项目接口.md", "verdict_4"),
    ("流程/04 项目计划/模板_WBS.md", "sop_stage"),
    ("流程/04 项目计划/模板_进度基线.md", "freeze_id"),
    ("流程/05 推进实施控制/模板_干预轮次卡.md", "一类证据"),
    ("流程/05 推进实施控制/模板_干预轮次卡.md", "treat_need_ids"),
    ("流程/05 推进实施控制/模板_周报.md", "verdict_4"),
    ("流程/06 交付物/模板_验收单.md", "verdict_4"),
    ("流程/06 交付物/模板_验收单.md", "freeze_id"),
    ("合同/案件合同卡.md", "G0"),
    ("合同/案件合同卡.md", "G6"),
    ("合同/案件合同卡.md", "G8"),
    ("agent_pm/engine.py", "01"),
    ("agent_pm/README.md", "guide"),
    ("agent_pm/guide.py", "材料放哪"),
    ("agent_pm/README.md", "decide"),
    ("agent_pm/agents/HUMAN.md", "APPROVE"),
    ("agent_pm/engine.py", "only human may APPROVE"),
)

# writer file must contain its field (from 核心合同字段.csv)
CHAIN_READERS = (
    ("流程/04 项目计划/模板_WBS.md", "treat_need_ids"),
    ("流程/05 推进实施控制/README.md", "holdout_need_ids"),
    ("流程/06 交付物/模板_验收单.md", "primary_endpoint"),
    ("流程/06 交付物/模板_验收单.md", "platforms_required"),
    ("流程/07 预算和资源管理/工时标准.md", "platforms_required"),
    ("流程/08 沟通/沟通矩阵.md", "comms_bound"),
    ("流程/09 收尾/模板_结项报告.md", "close_no_reopen_l1"),
)

DRIFT = (
    ("流程/03 测量/项目接口.md", "上者 + `retest`"),
    ("合同/核心合同.md", "上者 + `retest`"),
    ("流程/10 项目文件/AGENT.md", "拒绝入库和发布"),
    ("agent_pm/guide.py", "流程/03 测量/台账/samples.csv"),
    ("流程/03 测量/AGENT.md", "流程/03 测量/台账/samples.csv"),
)

MEASURE_DOC_ENTRY = (
    "流程/03 测量",
    "agent_pm/agents/03_measure.md",
    "agent_pm/guide.py",
)

MEASURE_SKIP_PREFIXES = (
    "流程/03 测量/案件/",
    "流程/03 测量/配置/冻结/",
    "流程/03 测量/出数/",
    "流程/03 测量/台账/",
    "流程/03 测量/样本/",
    "流程/03 测量/工具/",
)

MEASURE_SCAN_ALWAYS = {
    "流程/03 测量/案件/README.md",
    "流程/03 测量/配置/冻结/README.txt",
    "流程/03 测量/出数/报告模板.md",
}

# 仅这些共享模板允许出现扫描器会拦截的旧路径/命令写法。
MEASURE_ALLOWLIST = set()

RUNTIME_FORBIDDEN = (
    "配置/冻结/",
    "流程/03 测量/样本/",
    "流程/03 测量/台账/samples.csv",
    "流程/03 测量/出数/metrics_daily.csv",
    "流程/03 测量/出数/calibration.csv",
    "流程/03 测量/出数/did.csv",
    "流程/03 测量/出数/coverage.csv",
)

CLI_NEED_CASE = (
    "metrics_rollup.py",
    "make_checklist.py",
    "api_sentinel.py",
    "asset_deposit.py",
    "freeze_config.py",
)


def _is_cli_line(line: str, tool: str) -> bool:
    if tool not in line:
        return False
    return "python" in line or "--" in line


def drift_hits_in_text(text: str) -> list[str]:
    hits: list[str] = []
    for tok in RUNTIME_FORBIDDEN:
        if tok in text:
            hits.append(tok)
    for line in text.splitlines():
        for tool in CLI_NEED_CASE:
            if _is_cli_line(line, tool) and "--case-id" not in line:
                hits.append(f"{tool} missing --case-id")
        if _is_cli_line(line, "metrics_rollup.py") and "--project-id" not in line:
            hits.append("metrics_rollup.py missing --project-id")
    return hits


def _measure_rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _skip_measure_doc(root: Path, path: Path) -> bool:
    rel = _measure_rel(root, path)
    if rel in MEASURE_SCAN_ALWAYS:
        return False
    if rel in MEASURE_ALLOWLIST:
        return True
    return any(rel.startswith(p) for p in MEASURE_SKIP_PREFIXES)


def measure_doc_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for rel in MEASURE_DOC_ENTRY:
        p = root / rel
        if p.is_file():
            if p.suffix.lower() in {".md", ".py", ".txt"} and not _skip_measure_doc(root, p):
                out.append(p)
        elif p.is_dir():
            for x in p.rglob("*"):
                if not x.is_file() or x.suffix.lower() not in {".md", ".py", ".txt"}:
                    continue
                if _skip_measure_doc(root, x):
                    continue
                out.append(x)
    return out


def scan_measure_docs(root: Path) -> list[str]:
    found: list[str] = []
    for path in measure_doc_files(root):
        rel = _measure_rel(root, path)
        if rel in MEASURE_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for hit in drift_hits_in_text(text):
            found.append(f"{rel} still has {hit}")
    return found


def generic_files() -> list[Path]:
    out: list[Path] = []
    for p in GENERIC_ROOTS:
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(x for x in p.rglob("*") if x.is_file())
    return out


def main() -> int:
    missing = [rel for rel in REQUIRED if not (ROOT / rel).is_file()]
    leaks: list[str] = []
    for path in generic_files():
        text = path.read_text(encoding="utf-8")
        for word in BANNED:
            if word in text:
                leaks.append(f"{path.relative_to(ROOT)}:{word}")
    gate_miss = []
    for rel, token in GATES + CHAIN_READERS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if token not in text:
            gate_miss.append(f"{rel} missing {token}")
    csv_path = ROOT / "合同" / "核心合同字段.csv"
    if csv_path.is_file():
        import csv
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                writer = ROOT / (row.get("writer_file") or "")
                field = row.get("field") or ""
                if field and writer.is_file() and field not in writer.read_text(encoding="utf-8"):
                    gate_miss.append(f"{writer.relative_to(ROOT)} missing field {field}")
    print(f"root={ROOT}")
    print(f"required={len(REQUIRED)} missing={len(missing)}")
    print(f"generic_files={len(generic_files())} leaks={len(leaks)}")
    print(f"gate_miss={len(gate_miss)}")
    if missing:
        print("MISSING", *missing, sep="\n  ")
    if leaks:
        print("CLIENT_LEAK", *leaks, sep="\n  ")
    if gate_miss:
        print("GATE", *gate_miss, sep="\n  ")
    drift = []
    for rel, token in DRIFT:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if token in text:
            drift.append(f"{rel} still has {token}")
    drift.extend(scan_measure_docs(ROOT))
    print(f"drift={len(drift)}")
    if drift:
        print("DRIFT", *drift, sep="\n  ")
    if missing or leaks or gate_miss or drift:
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
