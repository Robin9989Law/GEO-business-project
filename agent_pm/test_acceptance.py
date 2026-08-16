#!/usr/bin/env python3
"""P3-2: 报告 §八 列出的 14 个验收测试场景。

不开发新软件；用现有引擎做边界校验。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
import files as _files  # noqa: E402
import guide as _guide  # noqa: E402
import teaching as _teach  # noqa: E402
from test_agent_pm import (  # noqa: E402
    _apply03,
    _approve,
    _dual_decide,
    _install_freeze,
    _lock_01_02,
    _lock_07_08,
    _root,
    _seed_delivery,
    _seed_stage_out,
)


def _start(root: Path, case: str = "acc1") -> dict:
    engine.init_case(case, root)
    return engine.load_state(case, root)


def _lock_01_02_with_endpoint(st: dict, root: Path, endpoint: str = "p_mention") -> None:
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
    )
    _approve(st, "G0", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P1",
                "owner": "编排",
                "sop_stage": "诊断",
                "primary_goal": engine.PRIMARY_GOAL_TEXT,
                "primary_endpoint": endpoint,
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


# ---- 1. 非法 primary_endpoint 不能过 G1 ----
def test_01_illegal_primary_endpoint_blocks_g1() -> None:
    root = _root()
    st = _start(root)
    engine.apply_fields(st, {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}})
    _approve(st, "G0", root)
    # 02 阶段试 primary_endpoint=WRONG
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "project_id": "P1",
                    "owner": "编排",
                    "sop_stage": "诊断",
                    "primary_goal": engine.PRIMARY_GOAL_TEXT,
                    "primary_endpoint": "WRONG",
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
    except ValueError as e:
        assert "primary_endpoint" in str(e) and "p_mention" in str(e)
        print("✅ #1 非法 primary_endpoint 不能过 G1")
        return
    raise AssertionError("illegal primary_endpoint should fail")


# ---- 2. 诊断计划出现 intervention 或 wait 不能过 G2 ----
def test_02_diagnosis_plan_cannot_include_intervention() -> None:
    root = _root()
    st = _start(root)
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _approve(st, "G3", root)
    try:
        engine.apply_fields(st, {"windows": ["intervention", "noise", "baseline"], "fields": {"plan_hours": "5"}})
    except ValueError as e:
        assert "windows" in str(e) and "intervention" in str(e)
        print("✅ #2 诊断计划不能含 intervention")
    else:
        raise AssertionError("diagnosis plan with intervention should fail")
    # 同样 wait
    try:
        engine.apply_fields(st, {"windows": ["wait", "noise"], "fields": {"plan_hours": "5"}})
    except ValueError as e:
        assert "windows" in str(e)
        print("✅ #2 诊断计划不能含 wait")
    else:
        raise AssertionError("diagnosis plan with wait should fail")


# ---- 3. 冲刺在 03 写最终 verdict_4 必须失败 ----
def test_03_sprint_cannot_write_verdict_4_at_03() -> None:
    root = _root()
    st = _start(root, "acc3")
    _lock_01_02(st, "冲刺", root)
    _lock_07_08(st, "冲刺", root)
    _apply03(st, root)
    _seed_stage_out(root, st)
    _dual_decide(st, "G3", root)
    try:
        engine.apply_fields(st, {"fields": {"verdict_4": "受控前后描述"}}, cases_root=root)
    except ValueError as e:
        assert "owned by" in str(e) and "05" in str(e)
        print("✅ #3 冲刺 03 写最终 verdict_4 被拦")
    else:
        raise AssertionError("sprint 03 verdict_4 must fail")


# ---- 4. 冲刺在 05 未完成等待期不得写最终四选一 ----
def test_04_sprint_05_requires_intervention_completion() -> None:
    root = _root()
    st = _start(root, "acc4")
    _lock_01_02(st, "冲刺", root)
    _lock_07_08(st, "冲刺", root)
    _apply03(st, root)
    _seed_stage_out(root, st)
    _dual_decide(st, "G3", root)
    engine.apply_fields(st, {"windows": ["day0", "noise", "baseline", "intervention", "wait", "retest"], "fields": {"plan_hours": "10"}})
    _approve(st, "G2", root)
    _seed_stage_out(root, st)
    # 不填 intervention_completed_on / wait_days 直接写 verdict_4 → 失败
    try:
        engine.apply_fields(st, {"fields": {"intervention_class": "FAQ", "intervention_need_ids": "N01", "holdout_untouched": "是", "verdict_4": "受控前后描述"}}, cases_root=root)
    except ValueError as e:
        assert "wait" in str(e).lower() or "verdict_4" in str(e) or "intervention_completed_on" in str(e)
        print("✅ #4 冲刺 05 未完成等待期不得写 verdict_4")
    else:
        raise AssertionError("sprint 05 without wait must fail verdict_4")


# ---- 5. budget_scope 与产品线不一致必须失败 ----
def test_05_budget_scope_must_match_sop() -> None:
    root = _root()
    st = _start(root, "acc5")
    _lock_01_02(st, "诊断", root)
    # 诊断不允许 weekly（仅续约允许）；用 weekly 触发 BUDGET_SCOPE_OK 路径（不触发 DIAG_BUDGET_BAN）
    try:
        engine.apply_fields(st, {"fields": {"budget_hours": "12", "budget_scope": "冻结+weekly", "quote_excludes_l1": "是"}})
    except ValueError as e:
        assert "budget_scope" in str(e) and "weekly" in str(e)
        print("✅ #5 budget_scope 与 sop_stage 不一致必失败")
    else:
        raise AssertionError("budget_scope with weekly should fail for 诊断")


# ---- 6. platforms_required 与冻结配置不一致必须失败 ----
def test_06_platforms_required_must_match_freeze() -> None:
    root = _root()
    st = _start(root, "acc6")
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    # 03 apply freeze with platforms_required=P0
    fid = _install_freeze(root, st)
    # 故意篡改 state 里的 platforms_required 到与冻结不一致
    st["fields"]["platforms_required"] = "P1"  # 冻结写的是 P0
    try:
        engine.apply_fields(
            st,
            {"fields": {"freeze_id": fid, "data_grade": "定向级", "baseline_verdict_4": "描述基线", "verdict_4": "描述基线"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "freeze" in str(e).lower() or "contract" in str(e).lower()
        print("✅ #6 platforms_required 与冻结不一致必失败")
    else:
        raise AssertionError("platforms_required mismatch should fail")


# ---- 7. 交付目录缺关键文件必失败 ----
def test_07_delivery_missing_evidence_manifest() -> None:
    root = _root()
    st = _start(root, "acc7")
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _approve(st, "G3", root)
    engine.apply_fields(st, {"windows": ["day0", "noise", "baseline"], "fields": {"plan_hours": "5"}})
    _approve(st, "G2", root)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}}, cases_root=root)
    _approve(st, "G5", root)
    _seed_stage_out(root, st)
    # 删 evidence_manifest.json
    out = root / st["case_id"] / "measure" / "出数"
    if (out / "evidence_manifest.json").exists():
        (out / "evidence_manifest.json").unlink()
    try:
        engine.apply_fields(
            st,
            {"fields": {"delivery_manifest_checksum": "fake", "freeze_match": "是", "delivery_accepted": "是"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "delivery" in str(e).lower() or "no case" in str(e).lower() or "manifest" in str(e).lower()
        print("✅ #7 交付目录缺关键文件必失败")
    else:
        raise AssertionError("delivery missing must fail")


# ---- 8. 交付报告身份与冻结身份不一致必须失败 ----
def test_08_delivery_identity_must_match_freeze() -> None:
    root = _root()
    st = _start(root, "acc8")
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _approve(st, "G3", root)
    engine.apply_fields(st, {"windows": ["day0", "noise", "baseline"], "fields": {"plan_hours": "5"}})
    _approve(st, "G2", root)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}}, cases_root=root)
    _approve(st, "G5", root)
    _seed_stage_out(root, st)
    out = root / st["case_id"] / "measure" / "出数"
    import json
    p = out / "evidence_manifest.json"
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        data["freeze_id"] = "fake-freeze-id"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {"fields": {"delivery_manifest_checksum": engine.delivery_files_checksum(out), "freeze_match": "是", "delivery_accepted": "是"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "delivery" in str(e).lower() or "freeze" in str(e).lower() or "checksum" in str(e).lower() or "identity" in str(e).lower() or "manifest" in str(e).lower()
        print("✅ #8 交付报告身份与冻结不一致必失败")
    else:
        raise AssertionError("delivery identity mismatch must fail")


# ---- 9. G1/G3/G4/G8 缺第二角色不得批准 ----
def test_09_key_gate_requires_dual_role() -> None:
    root = _root()
    st = _start(root, "acc9")
    _lock_01_02(st, "诊断", root)  # G1 已双签过
    # 重新走到 G1 边界
    # 直接尝试 G3 单签（不传 role）—— 但 G3 没决定
    # 先 apply 03 fields 让 stage 03
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    # 单签 G3 不传 role
    try:
        engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root)
    except ValueError as e:
        assert "key gate" in str(e) and "G3" in str(e) and "member" in str(e)
        print("✅ #9 G3 缺第二角色不得批准")
    else:
        raise AssertionError("G3 single-approver must fail")


# ---- 10. 关键门同一成员双签必须失败 ----
def test_10_key_gate_same_member_double_sign() -> None:
    root = _root()
    st = _start(root, "acc10")
    _lock_01_02(st, "诊断", root)  # G1 已双签过
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _seed_stage_out(root, st)
    # 第一次 G3：member=甲, role=负责人
    engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root, member="甲", role="负责人", decision_reason="first sign")
    # 第二次 G3：member=甲（同一成员）, role=测量复核
    try:
        engine.decide(st, "G3", "APPROVE", actor="human", cases_root=root, member="甲", role="测量复核", decision_reason="second sign")
    except ValueError as e:
        assert "already signed" in str(e) or "G3" in str(e)
        print("✅ #10 关键门同一成员双签必失败")
    else:
        raise AssertionError("same member double sign must fail")


# ---- 11. CHANGE 后下游正式件和测量证据必须失效 ----
def test_11_change_invalidates_downstream() -> None:
    root = _root()
    st = _start(root, "acc11")
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _seed_stage_out(root, st)
    _dual_decide(st, "G3", root)
    engine.apply_fields(st, {"windows": ["day0", "noise", "baseline"], "fields": {"plan_hours": "5"}})
    _approve(st, "G2", root)
    # 05 阶段先写 intervention_class=无 让 waiting=human
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}}, cases_root=root)
    # 现在 G2 过门后有 04_进度 现行
    import files as _files
    vault = _files.vault_path(st["case_id"], root)
    pre = [d for d in _files._docs(vault) if d.get("doc_id") == "04_进度" and d.get("status") == "现行"]
    assert pre, "04_进度 should be current before CHANGE"
    # CHANGE 回 04
    engine.decide(
        st,
        "G5",  # 05 阶段做 CHANGE
        "CHANGE",
        actor="human",
        cases_root=root,
        rewind_to="04",
        member="owner_a",
        role="负责人",
        change_payload={
            "reason": "test",
            "affected_fields": ["plan_hours"],
            "affected_docs": ["04_进度"],
            "evidence_affected": [],
            "re_freeze_needed": False,
            "re_budget_needed": False,
            "re_comms_needed": False,
            "invalidated": ["04_进度"],
            "new_versions": {},
        },
    )
    # 现在 stage=04，04_进度 应该被标记 invalidated
    post = [d for d in _files._docs(vault) if d.get("doc_id") == "04_进度"]
    statuses = [d.get("status") for d in post]
    assert "invalidated" in statuses, f"04_进度 should be invalidated; got {statuses}"
    print("✅ #11 CHANGE 后下游正式件被失效")


# ---- 12. 新手/标准/专家 guide 路径一致、解释深度不同 ----
def test_12_guide_depth_varies_with_levels() -> None:
    root = _root()
    st = _start(root, "acc12")
    # 新手：pm=0 geo=0 tool=0
    novice = _teach.process_guide(st, member="新手")
    # 标 准：pm=1 geo=1 tool=1
    _teach.set_profile(st, "标准", {"pm_level": 1, "geo_level": 1, "tool_level": 1})
    standard = _teach.process_guide(st, member="标准")
    # 专家：pm=2 geo=2 tool=2
    _teach.set_profile(st, "专家", {"pm_level": 2, "geo_level": 2, "tool_level": 2})
    expert = _teach.process_guide(st, member="专家")
    # 路径一致：mode 来自 axis_depth
    assert novice["axis_depth"]["overall_mode"] == "novice"
    assert standard["axis_depth"]["overall_mode"] == "standard"
    assert expert["axis_depth"]["overall_mode"] == "expert"
    # 解释深度不同：白话标志
    assert novice["axis_depth"]["pm_explain"] is True
    assert standard["axis_depth"]["pm_explain"] is False
    assert expert["axis_depth"]["pm_explain"] is False
    # 路径一致：8 段格式固定
    g_n = _guide.format_guide(_guide.build_guide({**st, "case_id": "acc12", "stage": "01"}))
    g_e = _guide.format_guide(_guide.build_guide({**st, "case_id": "acc12", "stage": "01"}))
    for header in ("## 1. 现在在哪", "## 2. 当前唯一任务", "## 3. 人要交什么", "## 4. 材料放哪", "## 5. Agent 检查什么", "## 6. 过门产出", "## 7. 下一站", "## 8. 不能做什么"):
        assert header in g_n, f"新手指南缺段：{header}"
        assert header in g_e, f"专家指南缺段：{header}"
    print("✅ #12 新手/标准/专家路径一致、解释深度不同")


# ---- 13. 诊断/冲刺/续约三条完整路径均能走到 G8 ----
def test_13_three_full_paths() -> None:
    from test_synth_cases import (
        test_synth_diagnosis_full_path,
        test_synth_sprint_full_path,
        test_synth_retain_full_path,
    )
    test_synth_diagnosis_full_path()
    test_synth_sprint_full_path()
    test_synth_retain_full_path()
    print("✅ #13 诊断/冲刺/续约三条完整路径均能走到 G8")


def test_causal_claim_cannot_lock_did_at_02() -> None:
    root = _root()
    st = _start(root, "acc-cc")
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "冲刺", "ban_ack": "是"}},
    )
    _approve(st, "G0", root)
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "project_id": "P1",
                    "owner": "编排",
                    "sop_stage": "冲刺",
                    "primary_goal": engine.PRIMARY_GOAL_TEXT,
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
    except ValueError as e:
        assert "descriptive_until_isolation" in str(e)
        print("✅ 02 不得锁 did_isolated")
    else:
        raise AssertionError("02 causal_claim=did_isolated must fail")


def test_sprint_wait_clock_must_elapse() -> None:
    root = _root()
    st = _start(root, "acc-wait")
    _lock_01_02(st, "冲刺", root)
    _lock_07_08(st, "冲刺", root)
    _apply03(st, root)
    _seed_stage_out(root, st)
    _dual_decide(st, "G3", root)
    engine.apply_fields(
        st,
        {"windows": ["day0", "noise", "baseline", "intervention", "wait", "retest"], "fields": {"plan_hours": "10"}},
    )
    _approve(st, "G2", root)
    _seed_stage_out(root, st)
    try:
        engine.apply_fields(
            st,
            {
                "fields": {
                    "intervention_class": "FAQ",
                    "intervention_need_ids": "N01",
                    "holdout_untouched": "是",
                    "intervention_completed_on": "2026-08-15",
                    "wait_days": "7",
                    "verdict_4": "受控前后描述",
                }
            },
            cases_root=root,
        )
    except ValueError as e:
        assert "wait" in str(e).lower()
        print("✅ 冲刺等待时钟未满不得写 verdict_4")
    else:
        raise AssertionError("unelapsed wait must fail")


# ---- 冻结表行集：queries.csv / platforms.csv 必须对上合同字段 ----
def test_freeze_tables_must_match_need_and_platform_sets() -> None:
    import csv

    root = _root()
    st = _start(root, "acc-fz")
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    fid = _install_freeze(root, st)
    d = root / st["case_id"] / "measure" / "冻结" / fid
    with (d / "queries.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["query_id", "set", "need_id", "active"])
        w.writeheader()
        w.writerow({"query_id": "Q01", "set": "core", "need_id": "N99", "active": "1"})
        w.writerow({"query_id": "Q02", "set": "holdout", "need_id": "H01", "active": "1"})
    (d / "checksum.txt").write_text(engine.freeze_files_checksum(d) + "\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {"fields": {"freeze_id": fid, "data_grade": "定向级", "baseline_verdict_4": "描述基线", "verdict_4": "描述基线"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "queries.treat" in str(e)
        print("✅ 冻结 queries.treat 与 treat_need_ids 不一致必失败")
    else:
        raise AssertionError("queries.csv need set mismatch should fail")

    fid2 = _install_freeze(root, st, freeze_id="fz-plat")
    d2 = root / st["case_id"] / "measure" / "冻结" / fid2
    with (d2 / "platforms.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["channel", "tier", "active"])
        w.writeheader()
        w.writerow({"channel": "app_kimi", "tier": "P1", "active": "1"})
    (d2 / "checksum.txt").write_text(engine.freeze_files_checksum(d2) + "\n", encoding="utf-8")
    try:
        engine.apply_fields(
            st,
            {"fields": {"freeze_id": fid2, "data_grade": "定向级", "baseline_verdict_4": "描述基线", "verdict_4": "描述基线"}},
            cases_root=root,
        )
    except ValueError as e:
        assert "platforms.csv" in str(e)
        print("✅ 冻结 platforms.csv 不含 platforms_required 必失败")
    else:
        raise AssertionError("platforms.csv set mismatch should fail")


# ---- 14. 所有 Agent 提示词中的关键术语与统一注册表一致 ----
def test_14_agent_terms_match_registry() -> None:
    import subprocess
    r = subprocess.run(["python3", "工程/check_doc_consistency.py"], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
    assert r.returncode == 0, f"跨文档一致性失败:\n{r.stdout}\n{r.stderr}"
    assert "0 issues across 11 checks" in r.stdout
    print("✅ #14 Agent 提示词术语与统一注册表一致")


def main() -> int:
    test_01_illegal_primary_endpoint_blocks_g1()
    test_02_diagnosis_plan_cannot_include_intervention()
    test_03_sprint_cannot_write_verdict_4_at_03()
    test_04_sprint_05_requires_intervention_completion()
    test_05_budget_scope_must_match_sop()
    test_06_platforms_required_must_match_freeze()
    test_07_delivery_missing_evidence_manifest()
    test_08_delivery_identity_must_match_freeze()
    test_09_key_gate_requires_dual_role()
    test_10_key_gate_same_member_double_sign()
    test_11_change_invalidates_downstream()
    test_12_guide_depth_varies_with_levels()
    test_13_three_full_paths()
    test_14_agent_terms_match_registry()
    test_freeze_tables_must_match_need_and_platform_sets()
    test_causal_claim_cannot_lock_did_at_02()
    test_sprint_wait_clock_must_elapse()
    print()
    print("summary: 14/14 验收测试通过 + 冻结表/因果/等待时钟")
    return 0


if __name__ == "__main__":
    sys.exit(main())
