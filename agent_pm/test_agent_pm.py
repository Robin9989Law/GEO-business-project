#!/usr/bin/env python3
"""驱动 shipped engine + run.main，不是重写规则。全流程 01→09。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
import run


def _root() -> Path:
    return Path(tempfile.mkdtemp(prefix="geo-case-"))


def _apply_cli(root: Path, case: str, payload: dict) -> int:
    jf = root / "p.json"
    jf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return run.main(["apply", case, "--json", str(jf), "--cases-root", str(root)])


def _lock_01_02(st: dict, sop: str = "诊断") -> None:
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": sop,
                "ban_ack": "是",
            }
        },
    )
    engine.decide(st, "G0", "APPROVE", actor="human")
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
    )
    engine.decide(st, "G1", "APPROVE", actor="human")


def _install_freeze(root: Path, st: dict, freeze_id: str = "fz-test") -> str:
    import csv

    f = st["fields"]
    d = root / st["case_id"] / "measure" / "冻结" / freeze_id
    d.mkdir(parents=True, exist_ok=True)
    proj_fields = [
        "project_id",
        "sop_stage",
        "vertical",
        "city",
        "client_code",
        "treat_need_ids",
        "holdout_need_ids",
        "platforms_required",
    ]
    with (d / "project.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=proj_fields)
        w.writeheader()
        w.writerow(
            {
                "project_id": f["project_id"],
                "sop_stage": f["sop_stage"],
                "vertical": f.get("vertical") or "v",
                "city": f.get("city") or "c",
                "client_code": f.get("client_code") or "x",
                "treat_need_ids": f["treat_need_ids"],
                "holdout_need_ids": f["holdout_need_ids"],
                "platforms_required": f["platforms_required"],
            }
        )
    for name in ("queries.csv", "aliases.csv", "facts.csv", "owned_sources.csv", "platforms.csv"):
        (d / name).write_text("id\n", encoding="utf-8")
    (d / "checksum.txt").write_text(engine.freeze_files_checksum(d) + "\n", encoding="utf-8")
    return freeze_id


def _apply03(st: dict, root: Path, extra: dict | None = None) -> None:
    fid = _install_freeze(root, st)
    fields = {
        "freeze_id": fid,
        "data_grade": "定向级",
        "baseline_verdict_4": "描述基线",
    }
    if st["fields"].get("sop_stage") != "冲刺":
        fields["verdict_4"] = "描述基线"
    if extra:
        fields.update(extra)
    engine.apply_fields(st, {"fields": fields}, cases_root=root)


def _lock_07_08(st: dict, sop: str = "诊断") -> None:
    scope = {"诊断": "冻结+噪声+基线+抽检", "冲刺": "冻结+噪声+基线+一类证据+复测", "续约": "weekly+calib"}[sop]
    engine.apply_fields(
        st,
        {
            "fields": {
                "budget_hours": "12",
                "budget_scope": scope,
                "quote_excludes_l1": "是",
            }
        },
    )
    engine.decide(st, "G6", "APPROVE", actor="human")
    engine.apply_fields(
        st,
        {
            "fields": {
                "stakeholder_decision": "客户决策人",
                "comms_cadence": "每周",
                "comms_bound": "不得宽于四选一",
                "comms_api_not_primary": "是",
            }
        },
    )
    engine.decide(st, "G7", "APPROVE", actor="human")


def test_walk_order_is_full_process() -> None:
    assert engine.STAGES == ("01", "02", "07", "08", "03", "04", "05", "06", "09")
    assert engine.GATE_AFTER["07"] == "G6"
    assert engine.GATE_AFTER["08"] == "G7"
    assert engine.GATE_AFTER["09"] == "G8"


def test_human_cannot_apply() -> None:
    root = _root()
    engine.init_case("c1", root)
    st = engine.load_state("c1", root)
    try:
        engine.apply_fields(st, {"fields": {"vertical": "v"}}, actor="human")
    except ValueError as e:
        assert "human" in str(e)
    else:
        raise AssertionError("human apply must fail")


def test_cannot_skip_g0() -> None:
    root = _root()
    assert run.main(["init", "c1", "--cases-root", str(root)]) == 0
    assert (
        _apply_cli(
            root,
            "c1",
            {
                "fields": {
                    "vertical": "品类A",
                    "city": "城A",
                    "client_code": "c",
                    "sop_stage_intent": "诊断",
                    "ban_ack": "是",
                }
            },
        )
        == 0
    )
    st = engine.load_state("c1", root)
    nxt = engine.next_action(st)
    assert nxt["waiting"] == "human" and nxt["gate"] == "G0"
    try:
        engine.apply_fields(st, {"fields": {"project_id": "P1"}})
    except ValueError as e:
        assert "waiting" in str(e)
    else:
        raise AssertionError("apply while waiting human must fail")
    st = engine.load_state("c1", root)
    try:
        engine.decide(st, "G0", "APPROVE", actor="agent")
    except ValueError as e:
        assert "human" in str(e)
    else:
        raise AssertionError("agent must not APPROVE")


def test_cannot_widen_stage() -> None:
    root = _root()
    engine.init_case("c2", root)
    st = engine.load_state("c2", root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
    )
    engine.decide(st, "G0", "APPROVE", actor="human")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "project_id": "P2",
                    "sop_stage": "冲刺",
                    "primary_goal": "在无品牌发现问上提高被正确提及的概率",
                    "primary_endpoint": "p_mention",
                    "causal_claim": "descriptive_until_isolation",
                    "control_design": "监测组",
                    "success_rule_diagnosis": "描述基线",
                    "success_rule_sprint": "受控前后描述",
                    "success_rule_retain": "不能下结论",
                    "owner": "编排",
                    "treat_need_ids": "N01",
                    "holdout_need_ids": "H01",
                    "platforms_required": "P0",
                }
            },
        )
    except ValueError as e:
        assert "widen" in str(e)
    else:
        raise AssertionError("widen must fail")


def test_g1_goes_to_budget_not_measure() -> None:
    root = _root()
    engine.init_case("c4", root)
    st = engine.load_state("c4", root)
    _lock_01_02(st)
    nxt = engine.next_action(st)
    assert nxt["stage"] == "07"
    assert nxt["folder"] == "流程/07 预算和资源管理"
    assert "G3" not in nxt["gate"]


def test_diagnosis_budget_cannot_include_intervention() -> None:
    root = _root()
    engine.init_case("c5", root)
    st = engine.load_state("c5", root)
    _lock_01_02(st, "诊断")
    try:
        engine.apply_fields(
            st,
            {"fields": {"budget_hours": "20", "budget_scope": "一类证据+干预", "quote_excludes_l1": "是"}},
        )
    except ValueError as e:
        assert "intervention" in str(e)
    else:
        raise AssertionError("diagnosis budget must reject intervention")
    try:
        engine.apply_fields(
            st,
            {"fields": {"budget_hours": "8", "budget_scope": "冻结+噪声+基线", "quote_excludes_l1": "否"}},
        )
    except ValueError as e:
        assert "L1" in str(e)
    else:
        raise AssertionError("quote must exclude L1")


def test_diagnosis_blocks_intervention_and_verdict() -> None:
    root = _root()
    engine.init_case("c3", root)
    st = engine.load_state("c3", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    assert engine.next_action(st)["stage"] == "03"
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(st, {"windows": ["intervention", "noise"]})
    except ValueError as e:
        assert "windows" in str(e)
    engine.apply_fields(st, {"windows": ["noise", "baseline"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(st, {"fields": {"intervention_class": "FAQ"}})
    except ValueError as e:
        assert "intervention" in str(e)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}})
    engine.decide(st, "G5", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(st, {"fields": {"verdict_4": "受控前后描述"}})
    except ValueError as e:
        assert "verdict_4" in str(e)
    engine.apply_fields(
        st,
        {
            "fields": {
                "verdict_4": "描述基线",
                "delivery_manifest_checksum": "abc123",
                "freeze_match": "是",
                "delivery_accepted": "是",
            }
        },
    )
    nxt = engine.next_action(st)
    assert nxt["waiting"] == "human" and nxt["gate"] == "G4"
    engine.decide(st, "G4", "APPROVE", actor="human", cases_root=root)
    nxt = engine.next_action(st)
    assert nxt["stage"] == "09" and nxt["waiting"] == "agent"
    try:
        engine.apply_fields(st, {"fields": {"close_assets_ok": "否", "close_no_reopen_l1": "是"}})
    except ValueError as e:
        assert "assets" in str(e)
    engine.apply_fields(
        st,
        {
            "fields": {
                "close_assets_ok": "是",
                "close_no_reopen_l1": "是",
                "close_manifest_ok": "是",
                "close_board_empty": "是",
                "close_archive_ok": "是",
                "verdict_4": "描述基线",
            }
        },
    )
    engine.decide(st, "G8", "APPROVE", actor="human", cases_root=root)
    assert engine.next_action(st)["waiting"] == "done"


def test_guide_tells_human_where_and_order() -> None:
    import guide

    root = _root()
    engine.init_case("g1", root)
    st = engine.load_state("g1", root)
    briefing = engine.next_action(st)["briefing"]
    assert "先做" in briefing and "材料放哪" in briefing
    assert "流程/01 客户初次洽谈/禁售清单.md" in briefing
    assert f"agent_pm/cases/g1/inbox/" in briefing
    assert "流程/10 项目文件/案件/g1/原始/01/" in briefing
    assert "流程/10 项目文件/案件/g1/中转/看板.md" in briefing
    g7 = dict(st)
    g7["stage"] = "07"
    g7["fields"] = {"sop_stage": "诊断"}
    text7 = guide.format_guide(guide.build_guide(g7))
    assert "预算" in text7 and "工时标准.md" in text7
    assert "G6" in text7
    g8 = dict(st)
    g8["stage"] = "08"
    g8["fields"] = {"sop_stage": "诊断"}
    text8 = guide.format_guide(guide.build_guide(g8))
    assert "不得宽于四选一" in text8
    g3 = dict(st)
    g3["stage"] = "03"
    g3["fields"] = {"sop_stage": "诊断"}
    mat = " ".join(m["put_at"] for m in guide.build_guide(g3)["materials"])
    assert "流程/03 测量/案件/" in mat
    assert "台账/samples.csv" in mat
    g5 = dict(st)
    g5["stage"] = "05"
    g5["fields"] = {"sop_stage": "诊断"}
    text = guide.format_guide(guide.build_guide(g5))
    assert "不要改" in text
    g9 = dict(st)
    g9["stage"] = "09"
    g9["fields"] = {"sop_stage": "诊断", "verdict_4": "描述基线"}
    text9 = guide.format_guide(guide.build_guide(g9))
    assert "资产移交" in text9 and "G8" in text9
    code = run.main(["guide", "g1", "--cases-root", str(root)])
    assert code == 0


def test_empty_apply_and_approve_fail() -> None:
    root = _root()
    engine.init_case("e1", root)
    st = engine.load_state("e1", root)
    try:
        engine.apply_fields(st, {"fields": {}})
    except ValueError as e:
        assert "missing required" in str(e)
    else:
        raise AssertionError("empty apply must fail")
    try:
        engine.apply_fields(st, {"fields": {"vertical": "v"}})
    except ValueError as e:
        assert "missing required" in str(e)
    st2 = engine.new_state("e2")
    st2["waiting"] = "human"
    try:
        engine.decide(st2, "G0", "APPROVE", actor="human")
    except ValueError as e:
        assert "missing required" in str(e)
    else:
        raise AssertionError("empty approve must fail")


def test_change_rewinds_and_allows_rewrite() -> None:
    root = _root()
    engine.init_case("ch1", root)
    st = engine.load_state("ch1", root)
    _lock_01_02(st, "诊断")
    assert st["fields"]["owner"] == "编排"
    engine.apply_fields(
        st,
        {"fields": {"budget_hours": "12", "budget_scope": "冻结+噪声+基线+抽检", "quote_excludes_l1": "是"}},
    )
    engine.decide(st, "G6", "CHANGE", actor="human", rewind_to="02", cases_root=root)
    assert st["stage"] == "02"
    assert st["waiting"] == "agent"
    assert "owner" not in st["fields"]
    assert "budget_hours" not in st["fields"]
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P3",
                "owner": "负责人",
                "sop_stage": "诊断",
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
    )
    assert st["fields"]["owner"] == "负责人"


def test_sprint_cannot_lock_l1_at_g3() -> None:
    root = _root()
    engine.init_case("sp1", root)
    st = engine.load_state("sp1", root)
    _lock_01_02(st, "冲刺")
    _lock_07_08(st, "冲刺")
    try:
        _apply03(st, root, extra={"verdict_4": "确认性 L1"})
    except ValueError as e:
        assert "05" in str(e) or "retest" in str(e)
    else:
        raise AssertionError("sprint must not lock L1 at 03")


def test_demo_freeze_cannot_pass_other_project() -> None:
    root = _root()
    engine.init_case("df1", root)
    st = engine.load_state("df1", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "freeze_id": "2026-08-16",
                    "data_grade": "定向级",
                    "baseline_verdict_4": "描述基线",
                    "verdict_4": "描述基线",
                }
            },
            cases_root=root,
        )
    except ValueError as e:
        assert "freeze" in str(e)
    else:
        raise AssertionError("demo freeze must not pass other project")


def _to_sprint_g5(root: Path, case: str) -> dict:
    engine.init_case(case, root)
    st = engine.load_state(case, root)
    _lock_01_02(st, "冲刺")
    _lock_07_08(st, "冲刺")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline", "intervention", "retest"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    return st


def _write_signed_evidence(root: Path, st: dict, *, invalidate: bool = False, did_over: dict | None = None, skip_manifest: bool = False) -> Path:
    import csv
    import hashlib

    out = root / st["case_id"] / "measure" / "出数"
    out.mkdir(parents=True, exist_ok=True)
    ident = {
        "case_id": st["case_id"],
        "project_id": st["fields"]["project_id"],
        "freeze_id": st["fields"]["freeze_id"],
        "config_checksum": st["fields"].get("config_checksum") or "x",
        "evidence_run_id": engine._metrics().next_evidence_run_id(out),
    }
    did_row = {
        "channel": "app_doubao",
        "metric": "mention",
        "pre": "2026-08-01",
        "post": "2026-08-10",
        "did": "0.20",
        "did_lo": "0.10",
        "did_hi": "0.30",
        "excludes_zero": "1",
        "n_treat_clusters": "2",
        "n_hold_clusters": "2",
        "causal_claim": "did_isolated",
        "verdict": "did_excludes_zero",
        **ident,
    }
    if did_over:
        did_row.update(did_over)
    did_fields = list(did_row.keys())
    with (out / "did.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=did_fields)
        w.writeheader()
        w.writerow(did_row)
    cov_row = {
        "channel": "app_doubao",
        "tier": "P0",
        "n_expected": "1",
        "n_present": "1",
        "missing": "",
        "complete": "1",
        **ident,
    }
    with (out / "coverage.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cov_row.keys()))
        w.writeheader()
        w.writerow(cov_row)
    if not skip_manifest:
        files = {
            "did.csv": hashlib.sha256((out / "did.csv").read_bytes()).hexdigest()[:16],
            "coverage.csv": hashlib.sha256((out / "coverage.csv").read_bytes()).hexdigest()[:16],
        }
        (out / "evidence_manifest.json").write_text(
            json.dumps({**ident, "files": files}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if invalidate:
        epoch = ident["evidence_run_id"]
        (out / "INVALIDATED.txt").write_text(
            f"rewind: outputs not current\nepoch={epoch}\n",
            encoding="utf-8",
        )
    else:
        engine.commit_fresh_evidence(out, ident)
    return out


def test_shared_freeze_not_runtime_fallback() -> None:
    import csv
    import shutil

    root = _root()
    engine.init_case("sf1", root)
    st = engine.load_state("sf1", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    fid = "sf-shared-only"
    shared = engine.FREEZE_ROOT / fid
    shared.mkdir(parents=True, exist_ok=True)
    f = st["fields"]
    try:
        with (shared / "project.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=[
                    "project_id",
                    "sop_stage",
                    "vertical",
                    "city",
                    "treat_need_ids",
                    "holdout_need_ids",
                    "platforms_required",
                ],
            )
            w.writeheader()
            w.writerow(
                {
                    "project_id": f["project_id"],
                    "sop_stage": f["sop_stage"],
                    "vertical": f.get("vertical") or "v",
                    "city": f.get("city") or "c",
                    "treat_need_ids": f["treat_need_ids"],
                    "holdout_need_ids": f["holdout_need_ids"],
                    "platforms_required": f["platforms_required"],
                }
            )
        (shared / "checksum.txt").write_text("shared\n", encoding="utf-8")
        assert engine.resolve_freeze_dir(fid, st["case_id"], root) is None
        try:
            engine.apply_fields(
                st,
                {
                    "fields": {
                        "freeze_id": fid,
                        "data_grade": "定向级",
                        "baseline_verdict_4": "描述基线",
                        "verdict_4": "描述基线",
                    }
                },
                cases_root=root,
            )
        except ValueError as e:
            assert "freeze" in str(e)
        else:
            raise AssertionError("shared freeze must not pass G3")
    finally:
        shutil.rmtree(shared, ignore_errors=True)


def test_invalidated_evidence_cannot_l1() -> None:
    root = _root()
    st = _to_sprint_g5(root, "inv1")
    _write_signed_evidence(root, st, invalidate=True)
    try:
        engine.apply_fields(
            st,
            {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "invalidated" in str(e)
    else:
        raise AssertionError("INVALIDATED evidence must not pass L1")


def test_change_then_fresh_output_can_l1() -> None:
    root = _root()
    engine.init_case("rw1", root)
    st = engine.load_state("rw1", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": "冲刺",
                "ban_ack": "是",
            }
        },
    )
    engine.decide(st, "G0", "APPROVE", actor="human")
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P3",
                "owner": "编排",
                "sop_stage": "冲刺",
                "primary_goal": "在无品牌发现问上提高被正确提及的概率",
                "primary_endpoint": "p_mention",
                "causal_claim": "did_isolated",
                "control_design": "监测组",
                "success_rule_diagnosis": "描述基线",
                "success_rule_sprint": "受控前后描述",
                "success_rule_retain": "不能下结论",
                "treat_need_ids": "N01",
                "holdout_need_ids": "H01",
                "platforms_required": "P0",
            }
        },
    )
    engine.decide(st, "G1", "APPROVE", actor="human")
    _lock_07_08(st, "冲刺")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline", "intervention", "retest"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    out = _write_signed_evidence(root, st)
    engine.apply_fields(
        st,
        {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
        cases_root=root,
    )
    assert st["waiting"] == "human"
    engine.decide(st, "G5", "CHANGE", actor="human", rewind_to="05", cases_root=root)
    assert (out / "INVALIDATED.txt").is_file()
    try:
        engine.apply_fields(
            st,
            {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "invalidated" in str(e)
    else:
        raise AssertionError("stale invalidated evidence must not pass")
    _write_signed_evidence(root, st)
    assert not (out / "INVALIDATED.txt").exists()
    engine.apply_fields(
        st,
        {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
        cases_root=root,
    )
    assert st["waiting"] == "human"
    assert st["fields"]["did_positive"] == "是"


def test_change_then_partial_output_cannot_lift() -> None:
    root = _root()
    engine.init_case("rw2", root)
    st = engine.load_state("rw2", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": "冲刺",
                "ban_ack": "是",
            }
        },
    )
    engine.decide(st, "G0", "APPROVE", actor="human")
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P3",
                "owner": "编排",
                "sop_stage": "冲刺",
                "primary_goal": "在无品牌发现问上提高被正确提及的概率",
                "primary_endpoint": "p_mention",
                "causal_claim": "did_isolated",
                "control_design": "监测组",
                "success_rule_diagnosis": "描述基线",
                "success_rule_sprint": "受控前后描述",
                "success_rule_retain": "不能下结论",
                "treat_need_ids": "N01",
                "holdout_need_ids": "H01",
                "platforms_required": "P0",
            }
        },
    )
    engine.decide(st, "G1", "APPROVE", actor="human")
    _lock_07_08(st, "冲刺")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline", "intervention", "retest"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    out = _write_signed_evidence(root, st)
    old_did = (out / "did.csv").read_bytes()
    old_cov = (out / "coverage.csv").read_bytes()
    engine.apply_fields(
        st,
        {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
        cases_root=root,
    )
    assert st["waiting"] == "human"
    engine.decide(st, "G5", "CHANGE", actor="human", rewind_to="05", cases_root=root)
    assert (out / "INVALIDATED.txt").is_file()
    assert not (out / "did.csv").exists()
    assert not (out / "coverage.csv").exists()
    dead = list((out / "失效").rglob("did.csv"))
    assert dead

    (out / "did.csv").write_bytes(old_did)
    ident = {
        "case_id": st["case_id"],
        "project_id": st["fields"]["project_id"],
        "freeze_id": st["fields"]["freeze_id"],
        "config_checksum": st["fields"].get("config_checksum") or "x",
        "evidence_run_id": engine._metrics().next_evidence_run_id(out),
    }
    import csv

    cov_row = {
        "channel": "app_doubao",
        "tier": "P0",
        "n_expected": "1",
        "n_present": "1",
        "missing": "",
        "complete": "1",
        **ident,
    }
    with (out / "coverage.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cov_row.keys()))
        w.writeheader()
        w.writerow(cov_row)
    assert engine.commit_fresh_evidence(out, ident) is False
    assert (out / "INVALIDATED.txt").is_file()

    (out / "coverage.csv").write_bytes(old_cov)
    did_row = {
        "channel": "app_doubao",
        "metric": "mention",
        "pre": "2026-08-01",
        "post": "2026-08-10",
        "did": "0.20",
        "did_lo": "0.10",
        "did_hi": "0.30",
        "excludes_zero": "1",
        "n_treat_clusters": "2",
        "n_hold_clusters": "2",
        "causal_claim": "did_isolated",
        "verdict": "did_excludes_zero",
        **ident,
    }
    with (out / "did.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(did_row.keys()))
        w.writeheader()
        w.writerow(did_row)
    assert engine.commit_fresh_evidence(out, ident) is False
    assert (out / "INVALIDATED.txt").is_file()
    try:
        engine.apply_fields(
            st,
            {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "invalidated" in str(e)
    else:
        raise AssertionError("partial rewrite must not lift INVALIDATED")


def test_incomplete_freeze_and_fake_checksum_fail_g3() -> None:
    import csv

    root = _root()
    engine.init_case("fzbad", root)
    st = engine.load_state("fzbad", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    fid = "empty-scalars"
    d = root / st["case_id"] / "measure" / "冻结" / fid
    d.mkdir(parents=True, exist_ok=True)
    with (d / "project.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["project_id", "sop_stage", "city", "vertical", "platforms_required", "treat_need_ids", "holdout_need_ids"],
        )
        w.writeheader()
        w.writerow({k: "" for k in w.fieldnames})
    for name in ("queries.csv", "aliases.csv", "facts.csv", "owned_sources.csv", "platforms.csv"):
        (d / name).write_text("id\n", encoding="utf-8")
    (d / "checksum.txt").write_text("not-a-real-config-checksum\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "freeze_id": fid,
                    "data_grade": "定向级",
                    "baseline_verdict_4": "描述基线",
                    "verdict_4": "描述基线",
                }
            },
            cases_root=root,
        )
    except ValueError as e:
        msg = str(e)
        assert "freeze" in msg or "checksum" in msg
    else:
        raise AssertionError("empty freeze scalars / fake checksum must not pass G3")


def test_contradictory_did_cannot_l1() -> None:
    root = _root()
    st = _to_sprint_g5(root, "bad1")
    _write_signed_evidence(
        root,
        st,
        did_over={"did_lo": "-0.5", "excludes_zero": "0", "verdict": "did_excludes_zero"},
    )
    try:
        engine.apply_fields(
            st,
            {"fields": {"intervention_class": "FAQ", "verdict_4": "确认性 L1", "intervention_need_ids": "N01", "holdout_untouched": "是", "intervention_completed_on": "2026-08-01", "wait_days": "7"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "did_lo" in str(e) or "excludes_zero" in str(e)
    else:
        raise AssertionError("contradictory DiD must not pass L1")


def test_l1_without_did_csv_fails() -> None:
    root = _root()
    engine.init_case("l1", root)
    st = engine.load_state("l1", root)
    _lock_01_02(st, "冲刺")
    _lock_07_08(st, "冲刺")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline", "intervention", "retest"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "intervention_class": "FAQ",
                    "verdict_4": "确认性 L1",
                    "intervention_need_ids": "N01",
                    "holdout_untouched": "是",
                    "intervention_completed_on": "2026-08-01",
                    "wait_days": "7",
                    "did_excludes_zero": "是",
                    "did_positive": "是",
                    "treat_clusters": "2",
                    "holdout_clusters": "2",
                    "coverage_ok": "是",
                }
            },
            cases_root=root,
        )
    except ValueError as e:
        assert "did.csv" in str(e)
    else:
        raise AssertionError("L1 without did.csv must fail")


def test_need_overlap_blocked() -> None:
    root = _root()
    engine.init_case("ov1", root)
    st = engine.load_state("ov1", root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
    )
    engine.decide(st, "G0", "APPROVE", actor="human")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "project_id": "P3",
                    "owner": "编排",
                    "sop_stage": "诊断",
                    "primary_goal": "在无品牌发现问上提高被正确提及的概率",
                    "primary_endpoint": "p_mention",
                    "causal_claim": "descriptive_until_isolation",
                    "control_design": "监测组",
                    "success_rule_diagnosis": "描述基线",
                    "success_rule_sprint": "受控前后描述",
                    "success_rule_retain": "不能下结论",
                    "treat_need_ids": "N01;H01",
                    "holdout_need_ids": "H01",
                    "platforms_required": "P0",
                }
            },
        )
    except ValueError as e:
        assert "disjoint" in str(e) or "need" in str(e)
    else:
        raise AssertionError("overlapping needs must fail")


def test_plan_hours_cannot_exceed_budget() -> None:
    root = _root()
    engine.init_case("ph1", root)
    st = engine.load_state("ph1", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(st, {"windows": ["noise", "baseline"], "fields": {"plan_hours": "99"}})
    except ValueError as e:
        assert "plan_hours" in str(e) or "budget" in str(e)
    else:
        raise AssertionError("over-budget plan must fail")


def test_comms_api_primary_blocked() -> None:
    root = _root()
    engine.init_case("api1", root)
    st = engine.load_state("api1", root)
    _lock_01_02(st, "诊断")
    engine.apply_fields(
        st,
        {"fields": {"budget_hours": "12", "budget_scope": "冻结+噪声+基线+抽检", "quote_excludes_l1": "是"}},
    )
    engine.decide(st, "G6", "APPROVE", actor="human")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "stakeholder_decision": "客户决策人",
                    "comms_cadence": "每周",
                    "comms_bound": "不得宽于四选一",
                    "comms_api_not_primary": "否",
                }
            },
        )
    except ValueError as e:
        assert "API" in str(e)
    else:
        raise AssertionError("API-as-primary must fail")


def test_holdout_touched_and_foreign_need_blocked() -> None:
    root = _root()
    st = _to_sprint_g5(root, "ht1")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "intervention_class": "FAQ",
                    "verdict_4": "受控前后描述",
                    "intervention_need_ids": "N99",
                    "holdout_untouched": "是",
                    "intervention_completed_on": "2026-08-01",
                    "wait_days": "7",
                }
            },
        )
    except ValueError as e:
        assert "treat" in str(e) or "need" in str(e)
    else:
        raise AssertionError("foreign intervention need must fail")
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "intervention_class": "FAQ",
                    "verdict_4": "受控前后描述",
                    "intervention_need_ids": "N01",
                    "holdout_untouched": "否",
                    "intervention_completed_on": "2026-08-01",
                    "wait_days": "7",
                }
            },
        )
    except ValueError as e:
        assert "holdout" in str(e)
    else:
        raise AssertionError("touched holdout must fail")


def test_unaccepted_delivery_cannot_close() -> None:
    root = _root()
    engine.init_case("ua1", root)
    st = engine.load_state("ua1", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}})
    engine.decide(st, "G5", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "verdict_4": "描述基线",
                    "delivery_manifest_checksum": "abc",
                    "freeze_match": "是",
                    "delivery_accepted": "否",
                }
            },
        )
    except ValueError as e:
        assert "accepted" in str(e) or "delivery" in str(e)
    else:
        raise AssertionError("unaccepted delivery must fail")


def test_close_cannot_reopen_l1() -> None:
    root = _root()
    engine.init_case("cl1", root)
    st = engine.load_state("cl1", root)
    _lock_01_02(st, "诊断")
    _lock_07_08(st, "诊断")
    _apply03(st, root)
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"windows": ["noise", "baseline"], "fields": {"plan_hours": "10"}})
    engine.decide(st, "G2", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}})
    engine.decide(st, "G5", "APPROVE", actor="human", cases_root=root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "verdict_4": "描述基线",
                "delivery_manifest_checksum": "abc",
                "freeze_match": "是",
                "delivery_accepted": "是",
            }
        },
    )
    engine.decide(st, "G4", "APPROVE", actor="human", cases_root=root)
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "close_assets_ok": "是",
                    "close_no_reopen_l1": "是",
                    "close_manifest_ok": "是",
                    "close_board_empty": "是",
                    "close_archive_ok": "是",
                    "verdict_4": "确认性 L1",
                }
            },
        )
    except ValueError as e:
        assert "L1" in str(e) or "verdict" in str(e)
    else:
        raise AssertionError("close must not reopen L1")


if __name__ == "__main__":
    test_walk_order_is_full_process()
    test_human_cannot_apply()
    test_cannot_skip_g0()
    test_cannot_widen_stage()
    test_g1_goes_to_budget_not_measure()
    test_diagnosis_budget_cannot_include_intervention()
    test_diagnosis_blocks_intervention_and_verdict()
    test_guide_tells_human_where_and_order()
    test_empty_apply_and_approve_fail()
    test_change_rewinds_and_allows_rewrite()
    test_sprint_cannot_lock_l1_at_g3()
    test_demo_freeze_cannot_pass_other_project()
    test_shared_freeze_not_runtime_fallback()
    test_invalidated_evidence_cannot_l1()
    test_change_then_fresh_output_can_l1()
    test_change_then_partial_output_cannot_lift()
    test_incomplete_freeze_and_fake_checksum_fail_g3()
    test_need_overlap_blocked()
    test_plan_hours_cannot_exceed_budget()
    test_comms_api_primary_blocked()
    test_holdout_touched_and_foreign_need_blocked()
    test_unaccepted_delivery_cannot_close()
    test_close_cannot_reopen_l1()
    test_contradictory_did_cannot_l1()
    test_l1_without_did_csv_fails()
    print("ok")
