#!/usr/bin/env python3
"""学习档案与教学深度。怎么讲由 Agent 做；这里只锁模式和流程槽。"""

from __future__ import annotations

import json
from pathlib import Path

import engine

CONFIG_PATH = engine.ROOT / "合同" / "阶段教学与质检.json"
LEVELS = (0, 1, 2)
ACTIVITIES = (
    "onboarding",
    "material_pending",
    "agent_review",
    "rework_required",
    "appeal_pending",
    "agent_draft",
    "human_gate",
    "done",
)
FOCUS = {
    "01": "产品线与禁售",
    "02": "主终点和监测组",
    "07": "范围、人天和报价",
    "08": "对象与口径边界",
    "03": "冻结、噪声、App/API",
    "04": "WBS、依赖和预算",
    "05": "诊断/冲刺执行边界",
    "06": "验收一致性",
    "09": "资产脱敏和正式关项",
}
SLOTS_ALL = (
    "现在在哪、这一步为什么存在",
    "当前只需要完成的一件事",
    "用白话解释首次出现的 PM/GEO 概念",
    "一个通用合格示例和一个典型反例",
    "用户需要提交什么、放到哪里",
    "Agent 将按哪些标准检查",
    "完成后会发生什么，然后停下等待",
)
SLOTS_EXPERT = (
    "现在在哪、这一步为什么存在",
    "当前只需要完成的一件事",
    "用户需要提交什么、放到哪里",
    "Agent 将按哪些标准检查",
    "完成后会发生什么，然后停下等待",
)


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_process(state: dict) -> dict:
    state.setdefault("activity", "onboarding")
    state.setdefault("current_member", "")
    state.setdefault("profiles", {})
    state.setdefault(
        "review",
        {
            "current_id": "",
            "current_result": "",
            "current_stage": "",
            "current_checksum": "",
            "current_record_checksum": "",
            "seq": 0,
            "attempts": {},
            "failures": {},
        },
    )
    rev = state["review"]
    rev.setdefault("current_id", "")
    rev.setdefault("current_result", "")
    rev.setdefault("current_stage", "")
    rev.setdefault("current_checksum", "")
    rev.setdefault("current_record_checksum", "")
    rev.setdefault("seq", 0)
    rev.setdefault("attempts", {})
    rev.setdefault("failures", {})
    return state


def mode_of(pm_level: int, geo_level: int, tool_level: int) -> str:
    """保留旧接口：返回整体 mode。P2-1 起推荐用 axis_depth 决定按维度讲解深度。"""
    levels = (pm_level, geo_level, tool_level)
    if any(x == 0 for x in levels):
        return "novice"
    if all(x == 2 for x in levels):
        return "expert"
    return "standard"


def axis_depth(pm_level: int, geo_level: int, tool_level: int) -> dict:
    """P2-1: 按 PM/GEO/Tool 三轴分别返回讲解深度（每轴 0=白话+示例 / 1=检查清单 / 2=差异提示）。

    返回 dict:
      pm: 0/1/2
      geo: 0/1/2
      tool: 0/1/2
      pm_explain / geo_explain / tool_explain: bool（本轴是否给白话+示例）
      overall_mode: novice / standard / expert（向后兼容）
    """
    def explain(level: int) -> bool:
        return level == 0

    return {
        "pm": int(pm_level),
        "geo": int(geo_level),
        "tool": int(tool_level),
        "pm_explain": explain(pm_level),
        "geo_explain": explain(geo_level),
        "tool_explain": explain(tool_level),
        "overall_mode": mode_of(pm_level, geo_level, tool_level),
    }


def _norm_level(val: object) -> int:
    try:
        n = int(val)
    except (TypeError, ValueError):
        engine._fail("level must be 0, 1 or 2")
    if n not in LEVELS:
        engine._fail("level must be 0, 1 or 2")
    return n


def blank_profile(member: str) -> dict:
    return {
        "member": member,
        "pm_level": 0,
        "geo_level": 0,
        "tool_level": 0,
        "mode": "novice",
        "style": "",
        "stage_novice": False,
        "first_pass_streak": 0,
        "updated_at": engine.now(),
    }


def get_profile(state: dict, member: str) -> dict | None:
    ensure_process(state)
    return state["profiles"].get((member or "").strip())


def effective_mode(profile: dict | None) -> str:
    if not profile:
        return "standard"
    style = profile.get("style") or ""
    if style == "finer":
        return "novice"
    if style == "shorter":
        return "expert"
    if profile.get("stage_novice"):
        return "novice"
    return profile.get("mode") or mode_of(
        int(profile.get("pm_level") or 0),
        int(profile.get("geo_level") or 0),
        int(profile.get("tool_level") or 0),
    )


def depth_flags(mode: str) -> dict:
    show = mode != "expert"
    return {
        "mode": mode,
        "concepts": show,
        "examples": show,
        "must": ["where", "one_task", "path", "checks", "next_gate"],
    }


def set_profile(state: dict, member: str, payload: dict) -> dict:
    ensure_process(state)
    member = (member or "").strip()
    if not member:
        engine._fail("member required")
    rec = state["profiles"].get(member) or blank_profile(member)
    if "pm_level" in payload:
        rec["pm_level"] = _norm_level(payload.get("pm_level"))
    if "geo_level" in payload:
        rec["geo_level"] = _norm_level(payload.get("geo_level"))
    if "tool_level" in payload:
        rec["tool_level"] = _norm_level(payload.get("tool_level"))
    style = payload.get("style")
    if style in {"finer", "shorter", ""}:
        rec["style"] = style or ""
    rec["mode"] = mode_of(rec["pm_level"], rec["geo_level"], rec["tool_level"])
    rec["member"] = member
    rec["updated_at"] = engine.now()
    state["profiles"][member] = rec
    state["current_member"] = member
    if state.get("activity") in {"", "onboarding"}:
        state["activity"] = "material_pending"
        if state.get("waiting") == "agent":
            pass
    state["log"].append({"at": engine.now(), "op": "profile", "member": member, "mode": rec["mode"]})
    return rec


def note_review_outcome(state: dict, member: str, result: str, first_attempt: bool) -> None:
    """P2-3: 记录表现但**不**自动升级 pm/geo/tool 等级；只能由人显式 promote_profile 升。"""
    rec = get_profile(state, member)
    if rec is None:
        return
    if result in {"REWORK", "HUMAN_REVIEW_REQUIRED"}:
        rec["stage_novice"] = True
        rec["first_pass_streak"] = 0
    elif result in {"PASS", "OVERRIDE_SOFT"} and first_attempt:
        rec["stage_novice"] = False
        rec["first_pass_streak"] = int(rec.get("first_pass_streak") or 0) + 1
    # 仅记录观察到的 streak，不自动提升
    rec.setdefault("observed_streaks", {})
    rec["updated_at"] = engine.now()


def promote_profile(state: dict, member: str, axis: str, level: int) -> dict:
    """P2-3: 人显式确认升级某一轴的能力（axis ∈ {pm, geo, tool}）。"""
    member = (member or "").strip()
    if not member:
        engine._fail("member required")
    if axis not in {"pm_level", "geo_level", "tool_level"}:
        engine._fail(f"bad axis {axis}; expected one of pm_level/geo_level/tool_level")
    rec = state["profiles"].get(member) or blank_profile(member)
    n = _norm_level(level)
    rec[axis] = n
    rec["mode"] = mode_of(rec["pm_level"], rec["geo_level"], rec["tool_level"])
    rec["updated_at"] = engine.now()
    rec["promoted_axes"] = list(rec.get("promoted_axes") or []) + [{"axis": axis, "to": n, "at": engine.now()}]
    state["profiles"][member] = rec
    return rec


def process_guide(state: dict, member: str = "") -> dict:
    ensure_process(state)
    member = (member or state.get("current_member") or "").strip()
    profile = get_profile(state, member) if member else None
    mode = effective_mode(profile)
    flags = depth_flags(mode)
    stage = state.get("stage") or "01"
    slots = list(SLOTS_ALL if flags["concepts"] else SLOTS_EXPERT)
    # P2-1: 三轴讲解深度
    axis = axis_depth(
        int((profile or {}).get("pm_level") or 0),
        int((profile or {}).get("geo_level") or 0),
        int((profile or {}).get("tool_level") or 0),
    )
    return {
        "activity": state.get("activity") or "onboarding",
        "member": member,
        "mode": mode,
        "depth": flags,
        "axis_depth": axis,
        "teach_focus": FOCUS.get(stage, ""),
        "flow": load_config()["flow"],
        "slots": slots,
        "agent_teaches": True,
        "agent_reviews": True,
        "ask_onboarding": profile is None,
        "onboarding_questions": [
            "pm_level：项目管理熟不熟？0 没做过 / 1 跟过项目 / 2 能独立收口",
            "geo_level：GEO/测量熟不熟？0 没接触 / 1 听过口径 / 2 能读出数",
            "tool_level：文件和命令熟不熟？0 不会放文件 / 1 能按路径放 / 2 能自己跑 CLI",
        ]
        if profile is None
        else [],
    }
