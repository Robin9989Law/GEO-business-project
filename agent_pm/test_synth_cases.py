#!/usr/bin/env python3
"""P3-1: 三类合成案件（诊断/冲刺/续约）跑 01→09 全流程。

依赖 test_agent_pm.py 的 helper：直接 import。
不开发新软件；不破坏现有 test。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402
from test_agent_pm import (  # noqa: E402
    _approve,
    _apply03,
    _dual_decide,
    _change_decide,
    _install_freeze,
    _lock_01_02,
    _lock_07_08,
    _root,
    _seed_closeout,
    _seed_delivery,
    _seed_deposit,
    _seed_stage_out,
)


def _apply04(st: dict, root: Path, windows: list[str], plan_hours: int = 8, _skip_g3: bool = False) -> None:
    if not _skip_g3:
        _seed_stage_out(root, st)
        _dual_decide(st, "G3", root)
    engine.apply_fields(st, {"windows": windows, "fields": {"plan_hours": str(plan_hours)}})
    _approve(st, "G2", root)


def _apply03_retain(st: dict, root: Path) -> None:
    """续约 03 阶段：baseline_verdict_4=不能下结论 + verdict_4=不能下结论。"""
    fid = _install_freeze(root, st)
    engine.apply_fields(
        st,
        {"fields": {"freeze_id": fid, "data_grade": "定向级", "baseline_verdict_4": "不能下结论", "verdict_4": "不能下结论"}},
        cases_root=root,
    )
    _seed_delivery(root, st)


def _apply05_sprint(st: dict, root: Path) -> None:
    _seed_stage_out(root, st)
    engine.apply_fields(
        st,
        {
            "fields": {
                "intervention_class": "FAQ 调整",
                "intervention_need_ids": "N01",
                "holdout_untouched": "是",
                "intervention_completed_on": "2026-08-01",
                "wait_days": "7",
                "verdict_4": "受控前后描述",
            }
        },
        cases_root=root,
    )
    _dual_decide(st, "G5", root)


def _apply05_diagnosis(st: dict, root: Path) -> None:
    """诊断 05：intervention_class=无 + G5 单签 → 跳到 06。"""
    _seed_stage_out(root, st)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}}, cases_root=root)
    _approve(st, "G5", root)


def _apply05_retain(st: dict, root: Path) -> None:
    """续约 05：同诊断（intervention_class=无 + G5 单签）。"""
    _seed_stage_out(root, st)
    engine.apply_fields(st, {"fields": {"intervention_class": "无"}}, cases_root=root)
    _approve(st, "G5", root)


def _apply06(st: dict, root: Path) -> None:
    """06 阶段：抄入 delivery_manifest_checksum + freeze_match + delivery_accepted。"""
    import files as _files
    out = Path(root) / st["case_id"] / "measure" / "出数"
    manifest = engine.delivery_files_checksum(out)
    _seed_stage_out(root, st)
    engine.apply_fields(
        st,
        {
            "fields": {
                "delivery_manifest_checksum": manifest,
                "freeze_match": "是",
                "delivery_accepted": "是",
            }
        },
        cases_root=root,
    )
    _dual_decide(st, "G4", root)


def _apply09(st: dict, root: Path) -> None:
    _seed_closeout(root, st)
    _seed_deposit(root, st)
    engine.apply_fields(
        st,
        {
            "fields": {
                "close_assets_ok": "是",
                "close_no_reopen_l1": "是",
                "close_manifest_ok": "是",
                "close_board_empty": "是",
                "close_archive_ok": "是",
            }
        },
        cases_root=root,
    )
    _dual_decide(st, "G8", root)


# ---- 诊断 ----

def test_synth_diagnosis_full_path() -> None:
    root = _root()
    engine.init_case("diag1", root)
    st = engine.load_state("diag1", root)
    _lock_01_02(st, "诊断", root)
    _lock_07_08(st, "诊断", root)
    _apply03(st, root)
    _apply04(st, root, ["day0", "noise", "baseline"], plan_hours=8)
    _apply05_diagnosis(st, root)
    _apply06(st, root)
    _apply09(st, root)
    assert st["stage"] in {"09"} or st["waiting"] == "done", f"诊断应到 done；stage={st['stage']} waiting={st['waiting']}"
    assert st["fields"].get("sop_stage") == "诊断"
    assert st["fields"].get("verdict_4") in {"描述基线", "不能下结论"}, f"诊断 verdict_4 应在允许集；got={st['fields'].get('verdict_4')}"
    assert st["fields"].get("close_assets_ok") == "是"
    print("✅ 诊断合成案件：01→09 全流程，verdict_4=" + str(st["fields"].get("verdict_4")))


# ---- 冲刺 ----

def test_synth_sprint_full_path() -> None:
    root = _root()
    engine.init_case("spr1", root)
    st = engine.load_state("spr1", root)
    _lock_01_02(st, "冲刺", root)
    _lock_07_08(st, "冲刺", root)
    _apply03(st, root)  # 冲刺 03 只能写 baseline_verdict_4，不能写 verdict_4
    # 冲刺 03 G3 关键门双签后才能验
    _seed_stage_out(root, st)
    _dual_decide(st, "G3", root)
    # 验证：冲刺 03 阶段写 verdict_4 应失败（owner=05）
    try:
        engine.apply_fields(st, {"fields": {"verdict_4": "受控前后描述"}}, cases_root=root)
    except ValueError as e:
        assert "owned by" in str(e) and "05" in str(e)
        print("✅ 冲刺 03 写最终 verdict_4 被拦")
    else:
        raise AssertionError("冲刺 03 写 verdict_4 应失败")
    _apply04(st, root, ["day0", "noise", "baseline", "intervention", "wait", "retest"], plan_hours=10, _skip_g3=True)
    _apply05_sprint(st, root)  # 写复测后 verdict_4
    assert st["fields"].get("verdict_4") == "受控前后描述", f"冲刺最终 verdict_4 应=受控前后描述；got={st['fields'].get('verdict_4')}"
    _apply06(st, root)
    _apply09(st, root)
    assert st["waiting"] == "done", f"冲刺应到 done；waiting={st['waiting']}"
    assert st["fields"].get("sop_stage") == "冲刺"
    print("✅ 冲刺合成案件：01→09 全流程，verdict_4=" + str(st["fields"].get("verdict_4")))


# ---- 续约 ----

def test_synth_retain_full_path() -> None:
    root = _root()
    engine.init_case("ret1", root)
    st = engine.load_state("ret1", root)
    _lock_01_02(st, "续约", root)
    _lock_07_08(st, "续约", root)
    _apply03_retain(st, root)
    _apply04(st, root, ["day0", "weekly", "calib"], plan_hours=4)
    _apply05_retain(st, root)
    _apply06(st, root)
    _apply09(st, root)
    assert st["waiting"] == "done", f"续约应到 done；waiting={st['waiting']}"
    assert st["fields"].get("sop_stage") == "续约"
    assert st["fields"].get("verdict_4") == "不能下结论", f"续约 verdict_4 应=不能下结论；got={st['fields'].get('verdict_4')}"
    print("✅ 续约合成案件：01→09 全流程，verdict_4=" + str(st["fields"].get("verdict_4")))


def main() -> int:
    test_synth_diagnosis_full_path()
    test_synth_sprint_full_path()
    test_synth_retain_full_path()
    print()
    print("summary: 3/3 合成案件（诊断/冲刺/续约）跑通 01→09 全流程")
    return 0


if __name__ == "__main__":
    sys.exit(main())
