#!/usr/bin/env python3
"""教学档案与门前质检流程。不测 Agent 怎么讲，只测流程和门槛。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
import files
import review
import teaching
import test_agent_pm as tap


def _root() -> Path:
    return Path(tempfile.mkdtemp(prefix="geo-teach-"))


def _quality(n: int = 2) -> dict:
    return {k: n for k in review.QUALITY_DIMS}


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _deposit(st: dict, root: Path, text: str = "本案材料。\n") -> dict:
    n = int((st.get("review") or {}).get("seq") or 0) + 1
    src = _write(root / f"{st['case_id']}_{st['stage']}_{n}.md", text)
    return files.deposit_raw(st["case_id"], src, st["stage"], cases_root=root)


def _pass(st: dict, root: Path, member: str = "负责人", extra: dict | None = None) -> dict:
    extra = dict(extra or {})
    raw_id = extra.pop("raw_id", None)
    if not raw_id and not extra.get("draft_id") and not (extra.get("review_target") or {}).get("draft_id"):
        raw_id = _deposit(st, root)["raw_id"]
    payload = {"quality": _quality(2), "confidence": 0.95, "issues": [], "facts_missing": []}
    payload.update(extra)
    return review.submit_review(st, payload, member=member, raw_id=raw_id or "", cases_root=root)


def test_modes_change_depth_not_paths() -> None:
    root = _root()
    paths = None
    checks = None
    for member, levels, expect in (
        ("a0", (0, 1, 2), "novice"),
        ("a1", (1, 1, 1), "standard"),
        ("a2", (2, 2, 2), "expert"),
    ):
        engine.init_case(member, root)
        st = engine.load_state(member, root)
        teaching.set_profile(st, member, {"pm_level": levels[0], "geo_level": levels[1], "tool_level": levels[2]})
        assert teaching.effective_mode(teaching.get_profile(st, member)) == expect
        g = engine.next_action(st)["guide"]
        flags = g["process"]["depth"]
        assert flags["mode"] == expect
        assert flags["concepts"] is (expect != "expert")
        assert flags["examples"] is (expect != "expert")
        assert "path" in flags["must"] and "checks" in flags["must"]
        mats = tuple(m["put_at"].replace(member, "CASE") for m in g["materials"])
        if paths is None:
            paths = mats
            checks = tuple(review.QUALITY_DIMS)
        else:
            assert mats == paths
            assert tuple(review.QUALITY_DIMS) == checks
        if expect == "expert":
            assert "用白话解释首次出现的 PM/GEO 概念" not in g["process"]["slots"]
        else:
            assert "用白话解释首次出现的 PM/GEO 概念" in g["process"]["slots"]


def test_profiles_isolated_and_persist() -> None:
    root = _root()
    engine.init_case("p1", root)
    st = engine.load_state("p1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 0, "geo_level": 0, "tool_level": 0})
    teaching.set_profile(st, "操作员", {"pm_level": 2, "geo_level": 2, "tool_level": 2})
    engine.save_state(st, root)
    st2 = engine.load_state("p1", root)
    assert teaching.effective_mode(teaching.get_profile(st2, "负责人")) == "novice"
    assert teaching.effective_mode(teaching.get_profile(st2, "操作员")) == "expert"
    teaching.set_profile(st2, "负责人", {"style": "shorter"})
    assert teaching.effective_mode(teaching.get_profile(st2, "负责人")) == "expert"
    assert teaching.get_profile(st2, "操作员")["pm_level"] == 2


def test_hard_rules_ignore_claimed_pass() -> None:
    root = _root()
    engine.init_case("h1", root)
    st = engine.load_state("h1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 2, "geo_level": 2, "tool_level": 2})
    src = _write(root / "bad.md", "我们保证会被推荐上首页\n")
    raw = files.deposit_raw("h1", src, "01", cases_root=root)
    rec = review.submit_review(
        st,
        {
            "quality": _quality(2),
            "confidence": 0.99,
            "result": "PASS",
            "issues": [],
        },
        member="负责人",
        raw_id=raw["raw_id"],
        cases_root=root,
    )
    assert rec["result"] == "REWORK"
    assert rec["claimed_result"] == "PASS"
    assert rec["ui_band"] == "不合格"
    assert any(x["rule"] == "banned" for x in rec["hard_fails"])
    try:
        engine.apply_fields(st, {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}}, cases_root=root)
    except ValueError as e:
        assert "review" in str(e)
    else:
        raise AssertionError("REWORK must block apply")

    engine.init_case("h2", root)
    st2 = engine.load_state("h2", root)
    st2["stage"] = "02"
    rec2 = review.submit_review(
        st2,
        {"quality": _quality(2), "confidence": 0.99, "materials_present": False},
        member="负责人",
        raw_id=_deposit(st2, root)["raw_id"],
        cases_root=root,
    )
    assert rec2["result"] == "REWORK"
    assert any(x["rule"] == "required_materials" for x in rec2["hard_fails"])

    engine.init_case("h3", root)
    st3 = engine.load_state("h3", root)
    st3["stage"] = "02"
    st3["fields"] = {"sop_stage_intent": "诊断"}
    rec3 = review.submit_review(
        st3,
        {"quality": _quality(2), "confidence": 0.99, "fields": {"sop_stage": "冲刺"}},
        member="负责人",
        raw_id=_deposit(st3, root)["raw_id"],
        cases_root=root,
    )
    assert rec3["result"] == "REWORK"
    assert any(x["rule"] == "cross_stage" for x in rec3["hard_fails"])

    engine.init_case("h4", root)
    st4 = engine.load_state("h4", root)
    rec4 = review.submit_review(
        st4,
        {"quality": _quality(2), "confidence": 0.99, "raw_id": "R9999"},
        member="负责人",
        cases_root=root,
    )
    assert rec4["result"] == "REWORK"
    assert any(x["rule"] == "required_materials" for x in rec4["hard_fails"])


def test_quality_boundaries() -> None:
    hard = []
    good = _quality(2)
    assert review.compute_result(hard, good, 0.9) == "PASS"
    assert review.ui_band(True, good) == "合格"
    mid = {"completeness": 2, "correctness": 2, "consistency": 2, "traceability": 1, "executability": 1}
    assert review.compute_result(hard, mid, 0.9) == "PASS"
    assert review.ui_band(True, mid) == "基本合格"
    low = {"completeness": 2, "correctness": 2, "consistency": 1, "traceability": 1, "executability": 1}
    assert review.compute_result(hard, low, 0.9) == "REWORK"
    assert review.ui_band(True, low) == "不合格"
    zero = {"completeness": 0, "correctness": 2, "consistency": 2, "traceability": 2, "executability": 2}
    assert review.compute_result(hard, zero, 0.9) == "REWORK"
    assert review.compute_result(hard, good, 0.5) == "HUMAN_REVIEW_REQUIRED"
    assert review.compute_result([{"rule": "banned"}], good, 0.5) == "REWORK"
    for bad in (float("nan"), float("inf"), -0.1, 1.01, "x"):
        try:
            review.parse_confidence(bad)
        except ValueError as e:
            assert "0..1" in str(e)
        else:
            raise AssertionError(f"confidence {bad!r} must be rejected")
    try:
        review.compute_result(hard, good, float("nan"))
    except ValueError:
        pass
    else:
        raise AssertionError("NaN confidence must not PASS")


def test_rework_blocks_gate_agent_cannot_approve() -> None:
    root = _root()
    engine.init_case("r1", root)
    st = engine.load_state("r1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    review.submit_review(
        st,
        {"quality": _quality(0), "confidence": 0.9},
        member="负责人",
        raw_id=_deposit(st, root)["raw_id"],
        cases_root=root,
    )
    assert st["activity"] == "rework_required"
    try:
        engine.apply_fields(st, {"fields": {"vertical": "v"}}, cases_root=root)
    except ValueError as e:
        assert "review" in str(e)
    else:
        raise AssertionError("rework must block apply")
    st["waiting"] = "human"
    try:
        engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
    except ValueError as e:
        assert "review" in str(e)
    else:
        raise AssertionError("rework must block approve")
    _pass(st, root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
        cases_root=root,
    )
    try:
        engine.decide(st, "G0", "APPROVE", actor="agent", cases_root=root)
    except ValueError as e:
        assert "human" in str(e)
    else:
        raise AssertionError("agent must not APPROVE after PASS")


def test_third_fail_coaches_without_inventing() -> None:
    root = _root()
    engine.init_case("c1", root)
    st = engine.load_state("c1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 0, "geo_level": 0, "tool_level": 0})
    raw_id = _deposit(st, root)["raw_id"]
    payload = {"quality": _quality(1), "confidence": 0.9, "facts_missing": ["city"]}
    review.submit_review(st, payload, member="负责人", raw_id=raw_id, cases_root=root)
    rec2a = review.submit_review(st, payload, member="负责人", raw_id=raw_id, cases_root=root)
    assert rec2a["failure_count"] == 2
    assert not rec2a.get("coaching")
    rec = review.submit_review(st, payload, member="负责人", raw_id=raw_id, cases_root=root)
    assert rec["attempt"] == 3
    assert rec["failure_count"] == 3
    assert rec["coaching"] and rec["coaching"]["mode"] == "one_fact"
    assert "city" in rec["coaching"]["ask"]
    try:
        review.submit_review(
            st,
            {**payload, "fields": {"city": "编造的城"}},
            member="负责人",
            raw_id=raw_id,
            cases_root=root,
        )
    except ValueError as e:
        assert "invent" in str(e)
    else:
        raise AssertionError("must not invent missing facts")
    rec2 = review.submit_review(
        st,
        {**payload, "fields": {"city": "待确认"}},
        member="负责人",
        raw_id=raw_id,
        cases_root=root,
    )
    assert rec2["result"] == "REWORK"


def test_soft_appeal_and_hard_override_fail() -> None:
    root = _root()
    engine.init_case("a1", root)
    st = engine.load_state("a1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    rec = review.submit_review(
        st,
        {"quality": _quality(1), "confidence": 0.9},
        member="负责人",
        raw_id=_deposit(st, root)["raw_id"],
        cases_root=root,
    )
    assert rec["result"] == "REWORK"
    snap = review.review_dir("a1", "01", root) / f"{rec['review_id']}.json"
    before = snap.read_text(encoding="utf-8")
    appealed = review.appeal(st, rec["review_id"], "软性判断过严", cases_root=root)
    assert appealed.get("appeal", {}).get("reason")
    assert st["activity"] == "appeal_pending"
    resolved = review.resolve_review(st, rec["review_id"], "OVERRIDE_SOFT", actor="human", reason="可继续准备", cases_root=root)
    assert resolved["result"] == "OVERRIDE_SOFT"
    assert st["activity"] == "agent_draft"
    assert snap.read_text(encoding="utf-8") == before
    dest = review.review_dir("a1", "01", root)
    assert list(dest.glob(f"{rec['review_id']}.appeal.*.json"))
    assert list(dest.glob(f"{rec['review_id']}.resolve.*.json"))
    assert "OVERRIDE_SOFT" in (dest / list(dest.glob(f"{rec['review_id']}.resolve.*.md"))[0]).read_text(encoding="utf-8")
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
        cases_root=root,
    )


def test_reviews_append_with_checksum() -> None:
    root = _root()
    engine.init_case("k1", root)
    st = engine.load_state("k1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    a = _write(root / "v1.md", "第一稿\n")
    r1 = files.deposit_raw("k1", a, "01", title="v1", cases_root=root)
    rec1 = review.submit_review(st, {"quality": _quality(1), "confidence": 0.9}, member="负责人", raw_id=r1["raw_id"], cases_root=root)
    b = _write(root / "v2.md", "第二稿\n")
    r2 = files.deposit_raw("k1", b, "01", title="v2", cases_root=root)
    rec2 = review.submit_review(st, {"quality": _quality(2), "confidence": 0.95}, member="负责人", raw_id=r2["raw_id"], cases_root=root)
    assert rec1["review_id"] != rec2["review_id"]
    assert rec1["input_checksum"] != rec2["input_checksum"]
    dest = review.review_dir("k1", "01", root)
    assert (dest / f"{rec1['review_id']}.json").is_file()
    assert (dest / f"{rec1['review_id']}.md").is_file()
    assert (dest / f"{rec2['review_id']}.json").is_file()
    old = json.loads((dest / f"{rec1['review_id']}.json").read_text(encoding="utf-8"))
    assert old["raw_id"] == r1["raw_id"]
    assert old["input_checksum"] == rec1["input_checksum"]


def _walk(sop: str) -> None:
    root = _root()
    case = {"诊断": "wd", "冲刺": "ws", "续约": "wr"}[sop]
    engine.init_case(case, root)
    st = engine.load_state(case, root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    _pass(st, root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": sop, "ban_ack": "是"}},
        cases_root=root,
    )
    engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
    _pass(st, root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P3",
                "owner": "编排",
                "sop_stage": sop,
                "primary_goal": "在无品牌发现问上提高被正确提及的概率",
                "primary_endpoint": "p_mention",
                "causal_claim": "descriptive_until_isolation",
                "control_design": "监测组",
                "success_rule_diagnosis": "描述基线",
                "success_rule_sprint": "受控前后描述",
                "success_rule_retain": "不能下结论",
                "treat_need_ids": "N01",
                "holdout_need_ids": "H01",
                "platforms_required": "P0",
            }
        },
        cases_root=root,
    )
    engine.decide(st, "G1", "APPROVE", actor="human", cases_root=root)
    assert st["stage"] == "07"
    scope = {"诊断": "冻结+噪声+基线+抽检", "冲刺": "冻结+噪声+基线+一类证据+复测", "续约": "weekly+calib"}[sop]
    _pass(st, root)
    engine.apply_fields(st, {"fields": {"budget_hours": "12", "budget_scope": scope, "quote_excludes_l1": "是"}}, cases_root=root)
    engine.decide(st, "G6", "APPROVE", actor="human", cases_root=root)
    _pass(st, root)
    engine.apply_fields(
        st,
        {"fields": {"stakeholder_decision": "客户决策人", "comms_cadence": "每周", "comms_bound": "不得宽于四选一"}},
        cases_root=root,
    )
    engine.decide(st, "G7", "APPROVE", actor="human", cases_root=root)
    assert st["stage"] == "03"
    _pass(st, root)
    extra03 = {"verdict_4": "不能下结论"} if sop == "续约" else None
    tap._apply03(st, root, extra=extra03)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    windows = {"诊断": ["noise", "baseline"], "冲刺": ["noise", "baseline", "intervention", "retest"], "续约": ["weekly", "calib"]}[sop]
    _pass(st, root)
    engine.apply_fields(st, {"windows": windows}, cases_root=root)
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    _pass(st, root)
    klass = "无" if sop == "诊断" else ("FAQ" if sop == "冲刺" else "无")
    extra = {}
    if sop == "冲刺":
        extra["verdict_4"] = "受控前后描述"
    engine.apply_fields(st, {"fields": {"intervention_class": klass, **extra}}, cases_root=root)
    engine.decide(st, "G5", "APPROVE", actor="human", cases_root=root)
    _pass(st, root)
    v = {"诊断": "描述基线", "冲刺": "受控前后描述", "续约": "不能下结论"}[sop]
    engine.apply_fields(st, {"fields": {"verdict_4": v}}, cases_root=root)
    engine.decide(st, "G4", "APPROVE", actor="human", cases_root=root)
    assert st["stage"] == "09"
    _pass(st, root)
    engine.apply_fields(st, {"fields": {"close_assets_ok": "是", "close_no_reopen_l1": "是", "verdict_4": v}}, cases_root=root)
    engine.decide(st, "G8", "APPROVE", actor="human", cases_root=root)
    assert engine.next_action(st)["waiting"] == "done"
    assert st["activity"] == "done"


def test_walks_cannot_skip() -> None:
    for sop in ("诊断", "冲刺", "续约"):
        _walk(sop)


def test_novice_follows_guide_only() -> None:
    root = _root()
    engine.init_case("n1", root)
    st = engine.load_state("n1", root)
    brief = engine.next_action(st)["briefing"]
    assert "开单先问" in brief
    assert "pm_level" in brief
    teaching.set_profile(st, "新人", {"pm_level": 0, "geo_level": 0, "tool_level": 0})
    g = engine.next_action(st)["guide"]
    assert g["mode"] == "novice"
    assert g["process"]["slots"]
    assert "材料放哪" in engine.next_action(st)["briefing"]
    put = g["put_inbox"]
    src = _write(root / "n1" / "inbox" / "01" / "原话.md", "客户想在无品牌发现问里被提到。\n")
    files.deposit_raw("n1", src, "01", cases_root=root)
    _pass(st, root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
        cases_root=root,
    )
    assert st["waiting"] == "human" and st["activity"] == "human_gate"
    engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
    assert st["stage"] == "02"
    assert put.endswith("inbox/")


def test_review_requires_target() -> None:
    root = _root()
    engine.init_case("need", root)
    st = engine.load_state("need", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    rec = review.submit_review(st, {"quality": _quality(2), "confidence": 0.95}, member="负责人", cases_root=root)
    assert rec["result"] == "REWORK"
    assert any(x["rule"] == "required_materials" for x in rec["hard_fails"])
    try:
        engine.apply_fields(
            st,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "review" in str(e)
    else:
        raise AssertionError("review without material must not apply")


def test_draft_target_and_checksum() -> None:
    import hashlib

    root = _root()
    engine.init_case("dr1", root)
    st = engine.load_state("dr1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    draft = _write(root / "dr1" / "out" / "01_草稿.md", "商机草稿，无禁售。\n")
    ck = hashlib.sha256(draft.read_bytes()).hexdigest()
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "01_草稿", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec["result"] == "PASS"
    assert rec["draft_id"] == "01_草稿"
    rec_bad = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "01_草稿", "draft_checksum": "0" * 64},
        member="负责人",
        cases_root=root,
    )
    assert rec_bad["result"] == "REWORK"
    assert any(x["rule"] == "draft_tampered" for x in rec_bad["hard_fails"])


def test_stale_soft_cannot_override_hard() -> None:
    root = _root()
    engine.init_case("stale", root)
    st = engine.load_state("stale", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    q1 = review.submit_review(
        st,
        {"quality": _quality(1), "confidence": 0.9},
        member="负责人",
        raw_id=_deposit(st, root)["raw_id"],
        cases_root=root,
    )
    assert q1["result"] == "REWORK"
    src = _write(root / "ban.md", "保证推荐\n")
    raw = files.deposit_raw("stale", src, "01", cases_root=root)
    q2 = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.99},
        member="负责人",
        raw_id=raw["raw_id"],
        cases_root=root,
    )
    assert q2["hard_fails"]
    assert st["review"]["current_id"] == q2["review_id"]
    try:
        review.resolve_review(st, q1["review_id"], "OVERRIDE_SOFT", actor="human", reason="用旧单", cases_root=root)
    except ValueError as e:
        assert "current" in str(e) or "activity" in str(e)
    else:
        raise AssertionError("stale OVERRIDE_SOFT must fail")
    try:
        review.appeal(st, q2["review_id"], "想覆盖硬规则", cases_root=root)
    except ValueError as e:
        assert "hard" in str(e)
    try:
        review.resolve_review(st, q2["review_id"], "OVERRIDE_SOFT", actor="human", reason="算了", cases_root=root)
    except ValueError as e:
        assert "hard" in str(e) or "activity" in str(e)
    else:
        raise AssertionError("hard override must fail")


def test_raw_tampered_is_hard_fail() -> None:
    root = _root()
    engine.init_case("tam", root)
    st = engine.load_state("tam", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    src = _write(root / "ok.md", "客户想被发现。\n")
    raw = files.deposit_raw("tam", src, "01", cases_root=root)
    vault = files.vault_path("tam", root)
    live = vault / "原始" / "01" / src.name
    live.write_text("已被改过。\n", encoding="utf-8")
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95},
        member="负责人",
        raw_id=raw["raw_id"],
        cases_root=root,
    )
    assert rec["result"] == "REWORK"
    assert any(x["rule"] == "raw_tampered" for x in rec["hard_fails"])
    assert rec["input_checksum"] != raw["checksum"]


def test_pass_then_two_fails_not_coaching() -> None:
    root = _root()
    engine.init_case("cnt", root)
    st = engine.load_state("cnt", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    _pass(st, root)
    raw = _deposit(st, root)["raw_id"]
    a = review.submit_review(st, {"quality": _quality(1), "confidence": 0.9}, member="负责人", raw_id=raw, cases_root=root)
    b = review.submit_review(st, {"quality": _quality(1), "confidence": 0.9}, member="负责人", raw_id=raw, cases_root=root)
    assert a["failure_count"] == 1
    assert b["failure_count"] == 2
    assert not b.get("coaching")


def test_human_review_md_and_done_locked() -> None:
    root = _root()
    engine.init_case("hr1", root)
    st = engine.load_state("hr1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.5},
        member="负责人",
        raw_id=_deposit(st, root)["raw_id"],
        cases_root=root,
    )
    assert rec["result"] == "HUMAN_REVIEW_REQUIRED"
    text = (review.review_dir("hr1", "01", root) / f"{rec['review_id']}.md").read_text(encoding="utf-8")
    assert "需人工复核（不是打回）" in text
    assert "0.5" in text
    st["waiting"] = "done"
    st["activity"] = "done"
    try:
        review.submit_review(
            st,
            {"quality": _quality(2), "confidence": 0.95},
            member="负责人",
            raw_id=_deposit(st, root)["raw_id"],
            cases_root=root,
        )
    except ValueError as e:
        assert "done" in str(e)
    else:
        raise AssertionError("done case must not accept review")


def test_pass_then_tamper_blocks_apply_and_approve() -> None:
    root = _root()
    engine.init_case("pt1", root)
    st = engine.load_state("pt1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    src = _write(root / "ok.md", "客户想被发现。\n")
    raw = files.deposit_raw("pt1", src, "01", cases_root=root)
    review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95},
        member="负责人",
        raw_id=raw["raw_id"],
        cases_root=root,
    )
    live = files.vault_path("pt1", root) / "原始" / "01" / src.name
    live.write_text("保证推荐\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "stale" in str(e) or "review" in str(e)
    else:
        raise AssertionError("tampered raw after PASS must not apply")

    engine.init_case("pt2", root)
    st2 = engine.load_state("pt2", root)
    teaching.set_profile(st2, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    src2 = _write(root / "ok2.md", "客户想被发现。\n")
    raw2 = files.deposit_raw("pt2", src2, "01", cases_root=root)
    review.submit_review(
        st2,
        {"quality": _quality(2), "confidence": 0.95},
        member="负责人",
        raw_id=raw2["raw_id"],
        cases_root=root,
    )
    engine.apply_fields(
        st2,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
        cases_root=root,
    )
    live2 = files.vault_path("pt2", root) / "原始" / "01" / src2.name
    live2.write_text("保证推荐\n", encoding="utf-8")
    try:
        engine.decide(st2, "G0", "APPROVE", actor="human", cases_root=root)
    except ValueError as e:
        assert "stale" in str(e) or "review" in str(e)
    else:
        raise AssertionError("tampered raw after PASS must not APPROVE")
    assert st2["stage"] == "01"


def test_draft_pass_then_tamper_blocks_apply_and_approve() -> None:
    import hashlib

    root = _root()
    engine.init_case("dt1", root)
    st = engine.load_state("dt1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    draft = _write(root / "dt1" / "out" / "01_草稿.md", "商机草稿，无禁售。\n")
    ck = hashlib.sha256(draft.read_bytes()).hexdigest()
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "01_草稿", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec["result"] == "PASS"
    assert rec.get("draft_path") == "out/01_草稿.md"
    draft.write_text("保证推荐\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "stale" in str(e) or "review" in str(e)
    else:
        raise AssertionError("tampered draft after PASS must not apply")

    engine.init_case("dt2", root)
    st2 = engine.load_state("dt2", root)
    teaching.set_profile(st2, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    draft2 = _write(root / "dt2" / "out" / "01_草稿.md", "商机草稿，无禁售。\n")
    ck2 = hashlib.sha256(draft2.read_bytes()).hexdigest()
    review.submit_review(
        st2,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "01_草稿", "draft_checksum": ck2},
        member="负责人",
        cases_root=root,
    )
    engine.apply_fields(
        st2,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
        cases_root=root,
    )
    draft2.write_text("保证推荐\n", encoding="utf-8")
    try:
        engine.decide(st2, "G0", "APPROVE", actor="human", cases_root=root)
    except ValueError as e:
        assert "stale" in str(e) or "review" in str(e)
    else:
        raise AssertionError("tampered draft after PASS must not APPROVE")
    assert st2["stage"] == "01"


def test_stage01_cannot_review_out02() -> None:
    import hashlib

    root = _root()
    engine.init_case("x02", root)
    st = engine.load_state("x02", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    draft = _write(root / "x02" / "out" / "02" / "需求草稿.md", "商机草稿，无禁售。\n")
    ck = hashlib.sha256(draft.read_bytes()).hexdigest()
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "需求草稿", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec["result"] != "PASS"
    rec2 = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "out/02/需求草稿.md", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec2["result"] != "PASS"


def test_formal_current_cannot_be_draft() -> None:
    import hashlib

    root = _root()
    engine.init_case("fm1", root)
    st = engine.load_state("fm1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    vault = files.init_vault("fm1", root)
    formal = _write(vault / "正式" / "现行" / "已正式.md", "已过门正文，无禁售。\n")
    ck = hashlib.sha256(formal.read_bytes()).hexdigest()
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "已正式", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec["result"] != "PASS"


def test_cli_void_review_persists_and_requires_rereview() -> None:
    import run

    root = _root()
    case = "cli-void"
    assert run.main(["init", case, "--cases-root", str(root)]) == 0
    pf = root / "p.json"
    pf.write_text(json.dumps({"pm_level": 1, "geo_level": 1, "tool_level": 1}), encoding="utf-8")
    assert run.main(["profile", case, "--member", "负责人", "--json", str(pf), "--cases-root", str(root)]) == 0
    st0 = engine.load_state(case, root)
    raw = _deposit(st0, root)
    live = files.vault_path(case, root) / "原始" / "01" / raw["filename"]
    original = live.read_text(encoding="utf-8")
    rf = root / "r.json"
    rf.write_text(json.dumps({"quality": _quality(2), "confidence": 0.95, "raw_id": raw["raw_id"]}), encoding="utf-8")
    assert run.main(["review", case, "--member", "负责人", "--raw-id", raw["raw_id"], "--json", str(rf), "--cases-root", str(root)]) == 0
    af = root / "a.json"
    af.write_text(
        json.dumps({"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}}),
        encoding="utf-8",
    )
    live.write_text("保证推荐\n", encoding="utf-8")
    assert run.main(["apply", case, "--json", str(af), "--cases-root", str(root)]) == 2
    st = engine.load_state(case, root)
    assert st["review"]["current_result"] == ""
    assert st["activity"] == "rework_required"
    live.write_text(original, encoding="utf-8")
    assert run.main(["apply", case, "--json", str(af), "--cases-root", str(root)]) == 2
    assert run.main(["review", case, "--member", "负责人", "--raw-id", raw["raw_id"], "--json", str(rf), "--cases-root", str(root)]) == 0
    assert run.main(["apply", case, "--json", str(af), "--cases-root", str(root)]) == 0
    st2 = engine.load_state(case, root)
    assert st2["waiting"] == "human"


def test_raw_registry_tamper_blocks_apply() -> None:
    root = _root()
    engine.init_case("reg1", root)
    st = engine.load_state("reg1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    raw = _deposit(st, root)
    review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95},
        member="负责人",
        raw_id=raw["raw_id"],
        cases_root=root,
    )
    vault = files.vault_path("reg1", root)
    rows = files._read_csv(vault / "原始" / "登记.csv", files.RAW_FIELDS)
    rows[0]["checksum"] = "0" * 64
    files._write_csv(vault / "原始" / "登记.csv", files.RAW_FIELDS, rows)
    try:
        engine.apply_fields(
            st,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except review.ReviewTargetStale:
        pass
    else:
        raise AssertionError("registry checksum edit must block apply")

    engine.init_case("reg2", root)
    st2 = engine.load_state("reg2", root)
    teaching.set_profile(st2, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    raw2 = _deposit(st2, root)
    review.submit_review(
        st2,
        {"quality": _quality(2), "confidence": 0.95},
        member="负责人",
        raw_id=raw2["raw_id"],
        cases_root=root,
    )
    vault2 = files.vault_path("reg2", root)
    src = vault2 / "原始" / "01" / raw2["filename"]
    dest_dir = vault2 / "原始" / "02"
    dest_dir.mkdir(parents=True, exist_ok=True)
    src.replace(dest_dir / raw2["filename"])
    rows2 = files._read_csv(vault2 / "原始" / "登记.csv", files.RAW_FIELDS)
    rows2[0]["stage"] = "02"
    files._write_csv(vault2 / "原始" / "登记.csv", files.RAW_FIELDS, rows2)
    try:
        engine.apply_fields(
            st2,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except review.ReviewTargetStale:
        pass
    else:
        raise AssertionError("registry stage move must block apply")


def test_draft_path_no_fallback() -> None:
    import hashlib

    root = _root()
    engine.init_case("dp1", root)
    st = engine.load_state("dp1", root)
    teaching.set_profile(st, "负责人", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    draft = _write(root / "dp1" / "out" / "01_草稿.md", "商机草稿，无禁售。\n")
    ck = hashlib.sha256(draft.read_bytes()).hexdigest()
    rec = review.submit_review(
        st,
        {"quality": _quality(2), "confidence": 0.95, "draft_id": "01_草稿", "draft_checksum": ck},
        member="负责人",
        cases_root=root,
    )
    assert rec.get("draft_path") == "out/01_草稿.md"
    text = draft.read_text(encoding="utf-8")
    draft.unlink()
    _write(root / "dp1" / "out" / "01_alt" / "01_草稿.md", text)
    try:
        engine.apply_fields(
            st,
            {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
            cases_root=root,
        )
    except review.ReviewTargetStale:
        pass
    else:
        raise AssertionError("missing draft_path must not fall back to draft_id")


def test_cli_profile_review() -> None:
    import run

    root = _root()
    assert run.main(["init", "cli1", "--cases-root", str(root)]) == 0
    pf = root / "p.json"
    pf.write_text(json.dumps({"pm_level": 0, "geo_level": 1, "tool_level": 2}), encoding="utf-8")
    assert run.main(["profile", "cli1", "--member", "负责人", "--json", str(pf), "--cases-root", str(root)]) == 0
    st0 = engine.load_state("cli1", root)
    raw = _deposit(st0, root)
    rf = root / "r.json"
    rf.write_text(json.dumps({"quality": _quality(2), "confidence": 0.95, "raw_id": raw["raw_id"]}), encoding="utf-8")
    assert run.main(["review", "cli1", "--member", "负责人", "--raw-id", raw["raw_id"], "--json", str(rf), "--cases-root", str(root)]) == 0
    st = engine.load_state("cli1", root)
    assert st["review"]["current_result"] == "PASS"


if __name__ == "__main__":
    test_modes_change_depth_not_paths()
    test_profiles_isolated_and_persist()
    test_hard_rules_ignore_claimed_pass()
    test_quality_boundaries()
    test_rework_blocks_gate_agent_cannot_approve()
    test_third_fail_coaches_without_inventing()
    test_soft_appeal_and_hard_override_fail()
    test_reviews_append_with_checksum()
    test_walks_cannot_skip()
    test_novice_follows_guide_only()
    test_review_requires_target()
    test_draft_target_and_checksum()
    test_stale_soft_cannot_override_hard()
    test_raw_tampered_is_hard_fail()
    test_pass_then_two_fails_not_coaching()
    test_human_review_md_and_done_locked()
    test_pass_then_tamper_blocks_apply_and_approve()
    test_draft_pass_then_tamper_blocks_apply_and_approve()
    test_stage01_cannot_review_out02()
    test_formal_current_cannot_be_draft()
    test_cli_void_review_persists_and_requires_rereview()
    test_raw_registry_tamper_blocks_apply()
    test_draft_path_no_fallback()
    test_cli_profile_review()
    print("ok")
