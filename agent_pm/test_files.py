#!/usr/bin/env python3
"""10 项目文件：原始入库、正式版本、中转。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
import files
import run


def _root() -> Path:
    return Path(tempfile.mkdtemp(prefix="geo-files-"))


def _write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_init_builds_three_zones() -> None:
    root = _root()
    engine.init_case("c1", root)
    vault = files.vault_path("c1", root)
    assert (vault / "原始" / "01").is_dir()
    assert (vault / "正式" / "现行").is_dir()
    assert (vault / "中转" / "看板.md").is_file()
    assert (vault / "正式" / "清单.csv").is_file()


def test_deposit_and_promote_versions() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "inbox.md", "客户原话：想被问到\n")
    raw = files.deposit_raw("c1", src, "01", title="客户原话", cases_root=root)
    assert raw["kind"] == "copy"
    vault = files.vault_path("c1", root)
    assert (vault / "原始" / "01" / src.name).is_file()
    v1 = files.promote_formal("c1", src, "01_商机卡", gate="G0", stage="01", cases_root=root)
    assert v1["rev"] == "1"
    v2 = files.promote_formal("c1", src, "01_商机卡", gate="G0", stage="01", cases_root=root)
    assert v2["rev"] == "2"
    assert (vault / "正式" / "版本" / "v001" / "01_商机卡.md").is_file()
    assert (vault / "正式" / "版本" / "v002" / "01_商机卡.md").is_file()
    assert (vault / "正式" / "现行" / "01_商机卡.md").is_file()
    docs = [d for d in files._docs(vault) if d["doc_id"] == "01_商机卡"]
    assert any(d["status"] == "历史" and d["rev"] == "1" for d in docs)
    assert any(d["status"] == "现行" and d["rev"] == "2" for d in docs)


def test_banned_claim_quarantined_not_rejected() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "bad.md", "我们保证会被推荐上首页\n")
    row = files.deposit_raw("c1", src, "01", cases_root=root)
    assert row["kind"] == "quarantine"
    vault = files.vault_path("c1", root)
    assert (vault / "原始" / "01" / "隔离" / "bad.md").is_file()
    try:
        files.promote_formal("c1", src, "01_商机卡", gate="G0", stage="01", cases_root=root)
    except ValueError as e:
        assert "banned" in str(e)
    else:
        raise AssertionError("banned claim must fail promote")


def test_measure_is_pointer_not_copy() -> None:
    root = _root()
    engine.init_case("c1", root)
    sample = _write(root / "流程" / "03 测量" / "样本" / "q.txt", "冷问原文\n")
    row = files.deposit_raw("c1", sample, "03", title="冷问", cases_root=root)
    assert row["kind"] == "pointer"
    dest = files.vault_path("c1", root) / "原始" / "03" / "q.ptr.md"
    assert dest.is_file()
    assert "指针" in dest.read_text(encoding="utf-8")
    assert not (files.vault_path("c1", root) / "原始" / "03" / "q.txt").exists()


def test_checkout_lock_and_checkin() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "doc.md", "章程草稿\n")
    files.promote_formal("c1", src, "02_章程", gate="G1", stage="02", cases_root=root)
    files.checkout("c1", "02_章程", "编排", cases_root=root)
    other = _write(root / "doc2.md", "别人改的\n")
    try:
        files.promote_formal("c1", other, "02_章程", gate="G1", stage="02", cases_root=root)
    except ValueError as e:
        assert "locked" in str(e)
    else:
        raise AssertionError("lock must block promote")
    newer = _write(root / "doc3.md", "编排改完\n")
    row = files.checkin("c1", "02_章程", newer, "编排", gate="G1", stage="02", cases_root=root)
    assert row["rev"] == "2"
    assert "02_章程" not in files._locks(files.vault_path("c1", root))


def test_exchange_drop_pick_ack() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "pack.md", "抽检包\n")
    dropped = files.drop_exchange("c1", src, "操作员", "评分", note="请抽检", cases_root=root)
    assert dropped["status"] == "待取"
    item = dropped["item_id"]
    b = files.board("c1", cases_root=root)
    assert any(x["item_id"] == item for x in b["pending"])
    try:
        files.pick_exchange("c1", item, "编排", cases_root=root)
    except ValueError as e:
        assert "评分" in str(e)
    picked = files.pick_exchange("c1", item, "评分", cases_root=root)
    assert picked["status"] == "已领取"
    acked = files.ack_exchange("c1", item, "评分", cases_root=root)
    assert acked["status"] == "已取"
    b2 = files.board("c1", cases_root=root)
    assert not any(x["item_id"] == item for x in b2["pending"])
    text = files.format_board(b)
    assert "待取" in text and "流程/10 项目文件/案件/c1/" in text


def test_decide_promotes_out() -> None:
    root = _root()
    engine.init_case("c1", root)
    st = engine.load_state("c1", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": "诊断",
                "ban_ack": "是",
            }
        },
    )
    out = root / "c1" / "out" / "01_商机卡.md"
    _write(out, "商机要点\n")
    engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
    vault = files.vault_path("c1", root)
    assert (vault / "正式" / "现行" / "01_商机卡.md").is_file()
    current = [d for d in files._docs(vault) if d["doc_id"] == "01_商机卡" and d["status"] == "现行"]
    assert current and current[0]["gate"] == "G0"


def test_promote_does_not_republish_prior_stage() -> None:
    root = _root()
    engine.init_case("c1", root)
    st = engine.load_state("c1", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": "诊断",
                "ban_ack": "是",
            }
        },
    )
    _write(root / "c1" / "out" / "01_商机卡.md", "商机要点\n")
    engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
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
                "treat_need_ids": "N01",
                "holdout_need_ids": "H01",
                "platforms_required": "P0",
            }
        },
    )
    _write(root / "c1" / "out" / "02_章程.md", "章程\n")
    # P1-2: 关键门双签
    for member, role in [("owner_a", "负责人"), ("owner_b", "GEO/验收专业复核")]:
        engine.decide(st, "G1", "APPROVE", actor="human", cases_root=root, member=member, role=role)
    vault = files.vault_path("c1", root)
    opp = [d for d in files._docs(vault) if d["doc_id"] == "01_商机卡"]
    assert len(opp) == 1 and opp[0]["stage"] == "01" and opp[0]["rev"] == "1"


def test_rewind_invalidates_formal() -> None:
    root = _root()
    engine.init_case("c1", root)
    st = engine.load_state("c1", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "vertical": "v",
                "city": "c",
                "client_code": "x",
                "sop_stage_intent": "诊断",
                "ban_ack": "是",
            }
        },
    )
    _write(root / "c1" / "out" / "01_商机卡.md", "商机要点\n")
    engine.decide(st, "G0", "APPROVE", actor="human", cases_root=root)
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
                "treat_need_ids": "N01",
                "holdout_need_ids": "H01",
                "platforms_required": "P0",
            }
        },
    )
    engine.decide(st, "G1", "CHANGE", actor="human", rewind_to="01", cases_root=root, member="owner_a", role="负责人", change_payload={
        "reason": "test change",
        "affected_fields": [],
        "affected_docs": ["01_商机卡"],
        "evidence_affected": [],
        "re_freeze_needed": False,
        "re_budget_needed": False,
        "re_comms_needed": False,
        "invalidated": ["01_商机卡"],
        "new_versions": {},
    })
    vault = files.vault_path("c1", root)
    docs = [d for d in files._docs(vault) if d["doc_id"] == "01_商机卡"]
    assert docs and docs[0]["status"] == "invalidated"
    current = vault / "正式" / "现行" / "01_商机卡.md"
    assert current.is_file()
    assert "已失效" in current.read_text(encoding="utf-8")
    dead = list((vault / "正式" / "失效").rglob("01_商机卡.md"))
    assert dead and "商机要点" in dead[0].read_text(encoding="utf-8")


def test_cli_key_gate_needs_member_and_role() -> None:
    root = _root()
    assert run.main(["init", "cli-g1", "--cases-root", str(root)]) == 0
    st = engine.load_state("cli-g1", root)
    engine.apply_fields(
        st,
        {"fields": {"vertical": "v", "city": "c", "client_code": "x", "sop_stage_intent": "诊断", "ban_ack": "是"}},
    )
    engine.save_state(st, root)
    assert run.main(["decide", "cli-g1", "--gate", "G0", "--verdict", "APPROVE", "--cases-root", str(root)]) == 0
    st = engine.load_state("cli-g1", root)
    engine.apply_fields(
        st,
        {
            "fields": {
                "project_id": "P1",
                "owner": "编排",
                "sop_stage": "诊断",
                "primary_goal": engine.PRIMARY_GOAL_TEXT,
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
    engine.save_state(st, root)
    assert run.main(["decide", "cli-g1", "--gate", "G1", "--verdict", "APPROVE", "--cases-root", str(root)]) == 2
    assert (
        run.main(
            [
                "decide",
                "cli-g1",
                "--gate",
                "G1",
                "--verdict",
                "APPROVE",
                "--member",
                "甲",
                "--role",
                "负责人",
                "--cases-root",
                str(root),
            ]
        )
        == 0
    )
    st = engine.load_state("cli-g1", root)
    assert st["gates"]["G1"]["verdict"] == "PENDING_DUAL"
    assert (
        run.main(
            [
                "decide",
                "cli-g1",
                "--gate",
                "G1",
                "--verdict",
                "APPROVE",
                "--member",
                "乙",
                "--role",
                "GEO/验收专业复核",
                "--cases-root",
                str(root),
            ]
        )
        == 0
    )
    st = engine.load_state("cli-g1", root)
    assert st["stage"] == "07"


def test_cli_board() -> None:
    root = _root()
    assert run.main(["init", "c1", "--cases-root", str(root)]) == 0
    src = _write(root / "a.md", "hello\n")
    assert run.main(["deposit", "c1", "--src", str(src), "--stage", "01", "--cases-root", str(root)]) == 0
    assert run.main(["board", "c1", "--cases-root", str(root)]) == 0


def test_csv_is_atomic_and_rejects_duplicate_keys() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "a.md", "客户原话\n")
    files.deposit_raw("c1", src, "01", cases_root=root)
    vault = files.vault_path("c1", root)
    reg = vault / "原始" / "登记.csv"
    assert not (vault / "原始" / "登记.csv.tmp").exists()
    rows = files._read_csv(reg, files.RAW_FIELDS)
    rows.append(dict(rows[0]))
    try:
        files._write_csv(reg, files.RAW_FIELDS, rows)
    except ValueError as e:
        assert "duplicate" in str(e)
    else:
        raise AssertionError("duplicate raw_id must fail")
    assert files._read_csv(reg, files.RAW_FIELDS)[0]["raw_id"] == "R0001"


def test_board_pair_and_check_vault() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "a.md", "客户原话\n")
    files.deposit_raw("c1", src, "01", title="客户原话", cases_root=root)
    files.promote_formal("c1", src, "01_商机卡", gate="G0", stage="01", cases_root=root)
    vault = files.vault_path("c1", root)
    assert (vault / "中转" / "看板.md").is_file()
    assert (vault / "中转" / "board.json").is_file()
    assert not (vault / "中转" / "看板.md.tmp").exists()
    assert not (vault / "中转" / "board.json.tmp").exists()
    report = files.check_vault("c1", cases_root=root)
    assert report["ok"], report
    assert report["catalog"]["raw"] == 1
    assert "01_商机卡" in [d["doc_id"] for d in files._docs(vault) if d["status"] == "现行"]
    assert run.main(["check-vault", "c1", "--cases-root", str(root)]) == 0


def test_check_vault_detects_missing_raw_and_board_drift() -> None:
    root = _root()
    engine.init_case("c1", root)
    src = _write(root / "a.md", "客户原话\n")
    files.deposit_raw("c1", src, "01", cases_root=root)
    vault = files.vault_path("c1", root)
    live = vault / "原始" / "01" / src.name
    live.unlink()
    report = files.check_vault("c1", cases_root=root)
    assert not report["ok"]
    assert any(e.startswith("raw_missing:") for e in report["errors"])
    extra = vault / "正式" / "现行" / "ghost.md"
    extra.write_text("未登记\n", encoding="utf-8")
    report2 = files.check_vault("c1", cases_root=root)
    assert any(e.startswith("unregistered:") for e in report2["errors"])


def _deposit_worker(case: str, path: str, root: str) -> None:
    files.deposit_raw(case, path, "01", cases_root=Path(root))


def test_concurrent_deposit_keeps_both_rows() -> None:
    import multiprocessing

    root = _root()
    engine.init_case("c1", root)
    a = _write(root / "a.md", "one\n")
    b = _write(root / "b.md", "two\n")
    ctx = multiprocessing.get_context("spawn")
    p1 = ctx.Process(target=_deposit_worker, args=("c1", str(a), str(root)))
    p2 = ctx.Process(target=_deposit_worker, args=("c1", str(b), str(root)))
    p1.start()
    p2.start()
    p1.join(10)
    p2.join(10)
    assert p1.exitcode == 0 and p2.exitcode == 0
    vault = files.vault_path("c1", root)
    rows = files._read_csv(vault / "原始" / "登记.csv", files.RAW_FIELDS)
    assert len(rows) == 2
    assert {r["raw_id"] for r in rows} == {"R0001", "R0002"}
    assert files.check_vault("c1", cases_root=root)["ok"]


if __name__ == "__main__":
    test_init_builds_three_zones()
    test_deposit_and_promote_versions()
    test_banned_claim_quarantined_not_rejected()
    test_measure_is_pointer_not_copy()
    test_checkout_lock_and_checkin()
    test_exchange_drop_pick_ack()
    test_decide_promotes_out()
    test_promote_does_not_republish_prior_stage()
    test_rewind_invalidates_formal()
    test_cli_key_gate_needs_member_and_role()
    test_cli_board()
    test_csv_is_atomic_and_rejects_duplicate_keys()
    test_board_pair_and_check_vault()
    test_check_vault_detects_missing_raw_and_board_drift()
    test_concurrent_deposit_keeps_both_rows()
    print("ok")
