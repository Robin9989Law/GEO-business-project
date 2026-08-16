#!/usr/bin/env python3
"""P2-4: 检查每个 agent 提示词是否满足 14 字段合同卡 schema（见 `合同/Agent 合同卡模板.md`）。

不修文件，只报告。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agent_pm" / "agents"

# 必填的 13 字段（"all" 阶段不强制 stage 字段名匹配，但必须存在）
REQUIRED_FIELDS = (
    "stage",
    "purpose",
    "entry_conditions",
    "read_sources",
    "human_inputs",
    "agent_writable_fields",
    "derived_fields",
    "hard_rules",
    "quality_dimensions",
    "formal_outputs",
    "gate",
    "handoff_to",
    "must_not",
)

STAGE_OF = {
    "00_orchestrator.md": "all",
    "01_intake.md": "01",
    "02_requirements.md": "02",
    "03_measure.md": "03",
    "04_plan.md": "04",
    "05_control.md": "05",
    "06_deliver.md": "06",
    "07_budget.md": "07",
    "08_comms.md": "08",
    "09_close.md": "09",
    "10_files.md": "all",
}

GATE_AFTER = {
    "01": "G0", "02": "G1", "07": "G6", "08": "G7",
    "03": "G3", "04": "G2", "05": "G5", "06": "G4", "09": "G8",
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter（最简化：只解析 key: value 或 key: [..]）。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    body = text[4:end]
    rest = text[end + 4:].lstrip("\n")
    fm: dict = {}
    current_key = ""
    current_list: list | None = None
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_list is not None:
            current_list.append(line[4:].strip())
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not m:
            current_list = None
            continue
        key, val = m.group(1), m.group(2).strip()
        current_key = key
        if val == "":
            fm[key] = []
            current_list = fm[key]
        elif val.startswith("[") and val.endswith("]"):
            items = [s.strip() for s in val[1:-1].split(",") if s.strip()]
            fm[key] = items
            current_list = None
        else:
            fm[key] = val
            current_list = None
    return fm, rest


def check_one(path: Path) -> list[str]:
    issues: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, _ = _parse_frontmatter(text)
    if not fm:
        issues.append("no YAML frontmatter (must start with --- ... ---)")
        return issues
    for field in REQUIRED_FIELDS:
        if field not in fm:
            issues.append(f"missing field: {field}")
            continue
        v = fm[field]
        if isinstance(v, list) and len(v) == 0:
            issues.append(f"empty list: {field}")
        elif isinstance(v, str) and not v.strip():
            issues.append(f"empty value: {field}")
    # 校验 stage 字段与文件名一致（除 "all"）
    expected = STAGE_OF.get(path.name, "")
    stage_v = str(fm.get("stage") or "").strip()
    if expected and expected != "all" and stage_v != expected:
        issues.append(f"stage mismatch: frontmatter says {stage_v!r}, file name implies {expected!r}")
    if expected and expected == "all" and stage_v not in {"all", "横切", ""}:
        issues.append(f"stage should be 'all' for cross-cutting, got {stage_v!r}")
    # 校验 gate 与 stage 一致
    expected_gate = GATE_AFTER.get(expected, "")
    if expected_gate:
        gate_v = str(fm.get("gate") or "").strip()
        if gate_v and gate_v != expected_gate:
            issues.append(f"gate mismatch: frontmatter says {gate_v!r}, expected {expected_gate!r} for stage {expected}")
    return issues


def main() -> int:
    if not AGENTS_DIR.is_dir():
        print(f"FAIL: agents dir not found: {AGENTS_DIR}")
        return 1
    files = sorted(AGENTS_DIR.glob("*.md"))
    # HUMAN.md 不是 agent，跳过
    files = [f for f in files if f.name != "HUMAN.md"]
    total = 0
    bad = 0
    for p in files:
        total += 1
        issues = check_one(p)
        if issues:
            bad += 1
            print(f"❌ {p.relative_to(ROOT)}")
            for it in issues:
                print(f"   - {it}")
        else:
            print(f"✅ {p.relative_to(ROOT)}")
    print()
    print(f"summary: {total - bad}/{total} agents have valid contract cards")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
