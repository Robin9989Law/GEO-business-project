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
    v1 = files.promote_formal("c1", src, "01_客户原话", gate="G0", stage="01", cases_root=root)
    assert v1["rev"] == "1"
    v2 = files.promote_formal("c1", src, "01_客户原话", gate="G0", stage="01", cases_root=root)
    assert v2["rev"] == "2"
    assert (vault / "正式" / "版本" / "v001" / "01_客户原话.md").is_file()
    assert (vault / "正式" / "版本" / "v002" / "01_客户原话.md").is_file()
    assert (vault / "正式" / "现行" / "01_客户原话.md").is_file()
    docs = [d for d in files._docs(vault) if d["doc_id"] == "01_客户原话"]
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
        files.promote_formal("c1", src, "01_违规", gate="G0", stage="01", cases_root=root)
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
    engine.decide(st, "G1", "APPROVE", actor="human", cases_root=root)
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
    engine.decide(st, "G1", "CHANGE", actor="human", rewind_to="01", cases_root=root)
    vault = files.vault_path("c1", root)
    docs = [d for d in files._docs(vault) if d["doc_id"] == "01_商机卡"]
    assert docs and docs[0]["status"] == "invalidated"
    current = vault / "正式" / "现行" / "01_商机卡.md"
    assert current.is_file()
    assert "已失效" in current.read_text(encoding="utf-8")
    dead = list((vault / "正式" / "失效").rglob("01_商机卡.md"))
    assert dead and "商机要点" in dead[0].read_text(encoding="utf-8")


def test_cli_board() -> None:
    root = _root()
    assert run.main(["init", "c1", "--cases-root", str(root)]) == 0
    src = _write(root / "a.md", "hello\n")
    assert run.main(["deposit", "c1", "--src", str(src), "--stage", "01", "--cases-root", str(root)]) == 0
    assert run.main(["board", "c1", "--cases-root", str(root)]) == 0


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
    test_cli_board()
    print("ok")
