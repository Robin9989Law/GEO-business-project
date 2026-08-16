#!/usr/bin/env python3
"""P2-5: 跨文档一致性检查（合同 vs 引擎 vs Agent 提示词 vs 阶段交付物注册）。

不修文件，只报告。返回非 0 退出码表示有 inconsistency。
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent_pm"))

import engine  # noqa: E402
import files as _files  # noqa: E402

CORE = ROOT / "合同" / "核心合同.md"
FIELDS_CSV = ROOT / "合同" / "核心合同字段.csv"
REGISTRY = ROOT / "合同" / "阶段交付物注册.md"
TEMPLATE = ROOT / "合同" / "Agent 合同卡模板.md"
AGENT_PY = ROOT / "agent_pm" / "files.py"
ENGINE_PY = ROOT / "agent_pm" / "engine.py"


def _md_contains(text: str, needle: str) -> bool:
    return needle in text


def check_1_stage_windows() -> list[str]:
    """核心合同 §1 战略推导表中的 sop_stage × 窗集合 vs engine.STAGE_WINDOWS。"""
    issues: list[str] = []
    md = CORE.read_text(encoding="utf-8")
    expected = {
        "诊断": {"day0", "noise", "baseline"},
        "冲刺": {"day0", "noise", "baseline", "intervention", "wait", "retest"},
        "续约": {"day0", "weekly", "calib"},
    }
    for sop, wins in expected.items():
        actual = engine.STAGE_WINDOWS.get(sop)
        if not actual:
            issues.append(f"engine.STAGE_WINDOWS missing {sop}")
            continue
        if set(actual) != wins:
            issues.append(f"STAGE_WINDOWS[{sop}] mismatch: engine={sorted(actual)} 合同期望={sorted(wins)}")
    return issues


def check_2_budget_scope() -> list[str]:
    issues: list[str] = []
    md = CORE.read_text(encoding="utf-8")
    for sop, wins in engine.BUDGET_SCOPE_OK.items():
        for w in wins:
            if w not in md:
                issues.append(f"BUDGET_SCOPE_OK[{sop}] token '{w}' not found in 核心合同.md")
    return issues


def check_3_success_rule() -> list[str]:
    issues: list[str] = []
    md = CORE.read_text(encoding="utf-8")
    for sop, wins in engine.SUCCESS_RULE_OK.items():
        for w in wins:
            if w not in md:
                issues.append(f"SUCCESS_RULE_OK[{sop}] value '{w}' not found in 核心合同.md")
    return issues


def check_4_causal_claim() -> list[str]:
    issues: list[str] = []
    md = CORE.read_text(encoding="utf-8")
    for c in engine.CAUSAL_CLAIM_OK:
        if c not in md:
            issues.append(f"CAUSAL_CLAIM_OK value '{c}' not found in 核心合同.md")
    if "descriptive_until_isolation" not in md:
        issues.append("descriptive_until_isolation not mentioned as default in 核心合同.md")
    return issues


def check_5_primary_goal_text() -> list[str]:
    issues: list[str] = []
    md = CORE.read_text(encoding="utf-8")
    if engine.PRIMARY_GOAL_TEXT not in md:
        issues.append(f"PRIMARY_GOAL_TEXT '{engine.PRIMARY_GOAL_TEXT}' not found in 核心合同.md")
    return issues


def check_6_fields_csv_match() -> list[str]:
    """核心合同字段.csv 的 writer_stage 与 engine.PRIMARY writers 字典（loaded by engine.load_writers）一致。"""
    issues: list[str] = []
    writers = engine.load_writers()
    with FIELDS_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            field = (row.get("field") or "").strip()
            stage = (row.get("writer_stage") or "").strip()
            if not field or not stage:
                continue
            csv_stages = frozenset(s for s in stage.split("|") if s)
            actual = writers.get(field)
            if actual is None:
                issues.append(f"field '{field}' in CSV not loadable by engine.load_writers")
                continue
            # verdict_4 在 engine._owner_for 里有特殊 hardcode，比较的是除 verdict_4 外的字段
            if field == "verdict_4":
                # CSV 应包含 03 和 05；engine._owner_for 按 sop 区分
                if "03" not in csv_stages or "05" not in csv_stages:
                    issues.append("verdict_4 writer_stage CSV should be 03|05")
            else:
                if csv_stages != actual:
                    issues.append(f"writer_stage mismatch for '{field}': CSV={sorted(csv_stages)} engine={sorted(actual)}")
    return issues


def check_7_registry_match() -> list[str]:
    """阶段交付物注册.md（Markdown 表）vs files.STAGE_DELIVERABLES 一致。"""
    issues: list[str] = []
    md = REGISTRY.read_text(encoding="utf-8")
    # 解析 markdown 表格：扫每行以 "| stage" 开头的行提取 doc_id
    declared: dict[str, set[str]] = {}
    for line in md.splitlines():
        m = re.match(r"^\|\s*(\d{2})\s*\|\s*`([^`]+)`\s*\|", line)
        if not m:
            continue
        stage = m.group(1)
        doc = m.group(2)
        if doc in {"doc_id", "stage", "—", ""}:
            continue
        declared.setdefault(stage, set()).add(doc)
    # 与 files.STAGE_DELIVERABLES 比
    for stage, docs in _files.STAGE_DELIVERABLES.items():
        csv_set = set(docs.keys())
        md_set = declared.get(stage, set())
        only_in_code = csv_set - md_set
        only_in_md = md_set - csv_set
        if only_in_code:
            issues.append(f"STAGE_DELIVERABLES[{stage}] has docs not in 注册表.md: {sorted(only_in_code)}")
        if only_in_md:
            issues.append(f"注册表.md has docs not in STAGE_DELIVERABLES[{stage}]: {sorted(only_in_md)}")
    return issues


def check_8_verdict4_source_in_agents() -> list[str]:
    """03/05/06/09 agent 提示词的 verdict_4 写入规则说明与核心合同 §1 verdict_4 字段所有权表一致。"""
    issues: list[str] = []
    expected_signals = {
        "agent_pm/agents/03_measure.md": [
            "baseline_verdict_4",
            ("本步可写", "本步禁止", "05 复测后"),
        ],
        "agent_pm/agents/05_control.md": [
            ("复测", "本步"),
            ("冲刺", "诊断/续约"),
        ],
        "agent_pm/agents/06_deliver.md": [
            ("抄入", "从 03 抄入", "从 05 复测后"),
        ],
        "agent_pm/agents/09_close.md": [
            ("回声", "回声 06"),
        ],
        "流程/03 测量/AGENT.md": [
            "baseline_verdict_4",
            ("05 复测后", "留给 05"),
        ],
        "流程/06 交付物/AGENT.md": [
            ("抄 03", "抄 05", "诊断/续约抄 03"),
        ],
        "流程/09 收尾/AGENT.md": [
            ("回声 06", "只回声"),
        ],
    }
    for rel, signal_groups in expected_signals.items():
        path = ROOT / rel
        if not path.is_file():
            issues.append(f"missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for grp in signal_groups:
            if isinstance(grp, str):
                if grp not in text:
                    issues.append(f"{rel} missing token: {grp!r}")
            else:
                if not any(s in text for s in grp):
                    issues.append(f"{rel} missing any of: {[repr(s) for s in grp]}")
    return issues


def check_11_dual_roles() -> list[str]:
    issues: list[str] = []
    path = ROOT / "合同" / "关键门双角色表.md"
    if not path.is_file():
        return ["missing 合同/关键门双角色表.md"]
    text = path.read_text(encoding="utf-8")
    for gate, roles in engine.GATE_REQUIRED_ROLES.items():
        if gate not in text:
            issues.append(f"双角色表 missing {gate}")
        for role in roles:
            if role not in text:
                issues.append(f"双角色表 missing role {role} for {gate}")
    for gate in engine.GATE_DUAL_APPROVERS:
        if gate not in text:
            issues.append(f"双角色表 missing dual gate {gate}")
    return issues


def check_10_glossary() -> list[str]:
    issues: list[str] = []
    path = ROOT / "合同" / "术语表.md"
    if not path.is_file():
        return ["missing 合同/术语表.md"]
    text = path.read_text(encoding="utf-8")
    for token in (
        "p_mention",
        "p_recommend",
        "App 可见性",
        "API 哨兵",
        "监测组",
        "噪声底",
        "受控前后描述",
        "确认性 L1",
        "项目账",
        "资产账",
        "descriptive_until_isolation",
    ):
        if token not in text:
            issues.append(f"术语表 missing {token!r}")
    return issues


def check_9_unit_uniform() -> list[str]:
    """所有 *hours 字段说明必须用"人时"；不能用"人天"裸词。"""
    issues: list[str] = []
    paths = [CORE, ROOT / "合同" / "案件合同卡.md", ROOT / "合同" / "项目流程SOP.md",
             ROOT / "合同" / "阶段交付物注册.md", ROOT / "合同" / "阶段教学与质检.json"]
    paths += sorted((ROOT / "agent_pm" / "agents").glob("*.md"))
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        # 排除 "1 人天 = 8 人时" 这种解释性出现
        for i, line in enumerate(text.splitlines(), 1):
            if "人天" in line and "1 人天" not in line and "8 人时" not in line:
                issues.append(f"{p.relative_to(ROOT)}:{i} 仍用 '人天' 而非 '人时': {line.strip()[:80]}")
    return issues


CHECKS = [
    ("STAGE_WINDOWS 一致 (核心合同 §1 ↔ engine)", check_1_stage_windows),
    ("BUDGET_SCOPE_OK 一致 (核心合同 §1 ↔ engine)", check_2_budget_scope),
    ("SUCCESS_RULE_OK 一致 (核心合同 §1 ↔ engine)", check_3_success_rule),
    ("CAUSAL_CLAIM_OK 一致 (核心合同 §1 ↔ engine)", check_4_causal_claim),
    ("PRIMARY_GOAL_TEXT 一致 (核心合同 §1 ↔ engine)", check_5_primary_goal_text),
    ("核心合同字段.csv ↔ engine.load_writers", check_6_fields_csv_match),
    ("阶段交付物注册.md ↔ files.STAGE_DELIVERABLES", check_7_registry_match),
    ("verdict_4 写入规则在各 agent 提示词中一致", check_8_verdict4_source_in_agents),
    ("单位统一：人时（不允许裸'人天'）", check_9_unit_uniform),
    ("术语表覆盖关键概念", check_10_glossary),
    ("关键门双角色表 ↔ engine.GATE_REQUIRED_ROLES", check_11_dual_roles),
]


def main() -> int:
    total_issues = 0
    for title, fn in CHECKS:
        issues = fn()
        status = "✅" if not issues else "❌"
        print(f"{status} {title}")
        for it in issues:
            print(f"   - {it}")
            total_issues += 1
    print()
    print(f"summary: {total_issues} issues across {len(CHECKS)} checks")
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
