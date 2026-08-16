#!/usr/bin/env python3
"""门禁、SOV、幂等、DiD、资产泄漏、推断的最小测试。"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import schema
from schema import SAMPLE_FIELDS, is_formal_row, metric_ready
from metrics_rollup import (
    COVER_OUT,
    OUT,
    apply_p0_mention_holm,
    cluster_resample_mean,
    coverage_from,
    did_from_rows,
    format_p0_coverage_fail,
    holm_adjust,
    invalidate_evidence,
    main,
    need_cluster_means,
    need_equal_mean,
    next_evidence_run_id,
    p0_coverage_gap,
    publish_evidence,
    query_mean,
    sov,
)
from asset_deposit import anon_project, leak_scan

FIXTURE_JSON = str(Path(__file__).resolve())


def _row(mention: str = "1", recommend: str = "0", extra: dict | None = None) -> dict:
    rec = {
        "limited": "0",
        "fresh_session": "1",
        "query_id": "Q01",
        "channel": "api_qwen_search",
        "raw_json_path": FIXTURE_JSON,
        "mention": mention,
        "recommend": recommend,
        "accuracy": "absent",
        "source_owned": "0",
        "competitor_hit": "0",
    }
    if extra:
        rec.update(extra)
    return rec


def test_unscored_not_formal() -> None:
    row = {
        "limited": "0",
        "fresh_session": "1",
        "query_id": "Q01",
        "channel": "api_qwen_search",
        "raw_json_path": FIXTURE_JSON,
        "mention": "1",
        "recommend": "",
        "accuracy": "absent",
        "source_owned": "0",
        "competitor_hit": "0",
    }
    ok, reason = is_formal_row(row, {"Q01": {"active": "1"}})
    assert not ok and reason == "unscored_recommend"


def test_empty_recommend_not_zero() -> None:
    row = {"limited": "0", "fresh_session": "1", "mention": "1", "recommend": "", "accuracy": "absent", "source_owned": "0", "competitor_hit": "0"}
    assert metric_ready(row, "recommend") is False


def test_sov_both_not_100() -> None:
    recs = []
    for i in range(4):
        recs.append(
            {
                "limited": "0",
                "fresh_session": "1",
                "query_id": "Q01",
                "channel": "api_qwen_search",
                "raw_json_path": FIXTURE_JSON,
                "mention": "1",
                "recommend": "1",
                "accuracy": "absent",
                "source_owned": "0",
                "competitor_hit": "1",
            }
        )
    v = sov(recs)
    assert v is not None and abs(v - 0.5) < 1e-9


def test_need_equal_weights() -> None:
    qmap = {
        "A1": {"need_id": "N01", "branded": "0"},
        "A2": {"need_id": "N01", "branded": "0"},
        "B1": {"need_id": "N02", "branded": "0"},
    }

    def row(m: str) -> dict:
        return {
            "limited": "0",
            "fresh_session": "1",
            "query_id": "x",
            "channel": "api_qwen_search",
            "raw_json_path": FIXTURE_JSON,
            "mention": m,
            "recommend": "0",
            "accuracy": "absent",
            "source_owned": "0",
            "competitor_hit": "0",
        }

    by_q = {
        "A1": [row("1"), row("1")],
        "A2": [row("1")],
        "B1": [row("0")],
    }
    # N01 mean=1, N02 mean=0 -> 0.5, not 0.75 response-weighted
    assert abs(need_equal_mean(qmap, by_q, "mention") - 0.5) < 1e-9


def test_anon_and_leak() -> None:
    a = anon_project("P202608-demo")
    assert a and a != "P202608-demo"
    hits = leak_scan("请联系示例培训学校 13800138000", {"示例培训学校"}, {"example.com"})
    assert any(h.startswith("brand:") for h in hits)
    assert "phone" in hits


def test_ledger_fields() -> None:
    assert "run_uuid" in SAMPLE_FIELDS and "top1_entity" in SAMPLE_FIELDS and "freeze_id" in SAMPLE_FIELDS


def test_cluster_reweight_counts_twice() -> None:
    qmap = {
        "A": {"need_id": "N01", "branded": "0"},
        "B": {"need_id": "N02", "branded": "0"},
        "C": {"need_id": "N03", "branded": "0"},
    }
    by_q = {
        "A": [_row("1")],
        "B": [_row("0")],
        "C": [_row("0")],
    }
    means = need_cluster_means(qmap, by_q, "mention")
    assert means == {"N01": 1.0, "N02": 0.0, "N03": 0.0}
    unique_avg = cluster_resample_mean(means, ["N01", "N03"])
    twice = cluster_resample_mean(means, ["N01", "N01", "N03"])
    assert unique_avg is not None and abs(unique_avg - 0.5) < 1e-9
    assert twice is not None and abs(twice - (2.0 / 3.0)) < 1e-9
    assert abs(twice - unique_avg) > 0.1


def test_did_insufficient_clusters() -> None:
    qmap = {
        "T1": {"need_id": "N01", "branded": "0", "active": "1"},
        "H1": {"need_id": "H01", "branded": "0", "active": "1"},
    }

    def app_row(day: str, qid: str, mention: str) -> dict:
        return {
            "limited": "0",
            "fresh_session": "1",
            "query_id": qid,
            "channel": "app_doubao",
            "date": day,
            "answer_text_path": FIXTURE_JSON,
            "screenshot_path": FIXTURE_JSON,
            "mention": mention,
            "recommend": "0",
            "accuracy": "absent",
            "source_owned": "0",
            "competitor_hit": "0",
        }

    rows = [
        app_row("2026-08-01", "T1", "1"),
        app_row("2026-08-02", "T1", "1"),
    ]
    out = did_from_rows(
        rows,
        qmap,
        {"N01"},
        {"H01"},
        "descriptive_until_isolation",
        "2026-08-01",
        "2026-08-02",
    )
    assert out
    assert all(r["verdict"] == "insufficient_clusters" for r in out)


def test_did_single_cluster_degenerate() -> None:
    qmap = {
        "T1": {"need_id": "N01", "branded": "0", "active": "1"},
        "H1": {"need_id": "H01", "branded": "0", "active": "1"},
    }

    def app_row(day: str, qid: str, mention: str) -> dict:
        return {
            "limited": "0",
            "fresh_session": "1",
            "query_id": qid,
            "channel": "app_doubao",
            "date": day,
            "answer_text_path": FIXTURE_JSON,
            "screenshot_path": FIXTURE_JSON,
            "mention": mention,
            "recommend": "0",
            "accuracy": "absent",
            "source_owned": "0",
            "competitor_hit": "0",
        }

    rows = [
        app_row("2026-08-01", "T1", "0"),
        app_row("2026-08-02", "T1", "1"),
        app_row("2026-08-01", "H1", "0"),
        app_row("2026-08-02", "H1", "0"),
    ]
    out = did_from_rows(rows, qmap, {"N01"}, {"H01"}, "did_isolated", "2026-08-01", "2026-08-02")
    assert out
    assert all(r["verdict"] == "degenerate_cluster" for r in out)
    assert all(r["excludes_zero"] == "" for r in out)


def test_did_negative_not_confirm() -> None:
    qmap = {
        "T1": {"need_id": "N01", "branded": "0", "active": "1"},
        "T2": {"need_id": "N02", "branded": "0", "active": "1"},
        "H1": {"need_id": "H01", "branded": "0", "active": "1"},
        "H2": {"need_id": "H02", "branded": "0", "active": "1"},
    }

    def app_row(day: str, qid: str, mention: str) -> dict:
        return {
            "limited": "0",
            "fresh_session": "1",
            "query_id": qid,
            "channel": "app_doubao",
            "date": day,
            "answer_text_path": FIXTURE_JSON,
            "screenshot_path": FIXTURE_JSON,
            "mention": mention,
            "recommend": "0",
            "accuracy": "absent",
            "source_owned": "0",
            "competitor_hit": "0",
        }

    rows = []
    for qid in ("T1", "T2"):
        rows.append(app_row("2026-08-01", qid, "1"))
        rows.append(app_row("2026-08-02", qid, "0"))
    for qid in ("H1", "H2"):
        rows.append(app_row("2026-08-01", qid, "0"))
        rows.append(app_row("2026-08-02", qid, "0"))
    out = did_from_rows(rows, qmap, {"N01", "N02"}, {"H01", "H02"}, "did_isolated", "2026-08-01", "2026-08-02")
    mention = [r for r in out if r["metric"] == "mention"]
    assert mention
    assert all(r["verdict"] == "did_negative" for r in mention)
    assert all(r["excludes_zero"] != "1" for r in mention)


def test_ledger_filter_by_project() -> None:
    from schema import filter_ledger

    rows = [
        {"project_id": "A", "freeze_id": "f1", "config_checksum": "x", "mention": "1"},
        {"project_id": "B", "freeze_id": "f1", "config_checksum": "x", "mention": "1"},
    ]
    only_a = filter_ledger(rows, project_id="A", freeze_id="f1", checksum="x")
    assert len(only_a) == 1 and only_a[0]["project_id"] == "A"


def test_coverage_ignores_limited() -> None:
    plats = [{"channel": "app_doubao", "tier": "P0"}]
    qids = ["Q01"]
    rows = [
        {
            "channel": "app_doubao",
            "query_id": "Q01",
            "date": "2026-08-16",
            "limited": "1",
            "fresh_session": "1",
        }
    ]
    cov = coverage_from(plats, qids, rows, "2026-08-16")
    assert cov[0]["complete"] == "0"


def test_cli_requires_case_id() -> None:
    import api_sentinel

    argv = sys.argv[:]
    try:
        sys.argv = ["api_sentinel.py", "--smoke"]
        try:
            api_sentinel.main()
        except SystemExit as e:
            msg = str(e)
            assert "case" in msg.lower() or e.code == 2
            return
        raise AssertionError("api_sentinel must require case-id")
    finally:
        sys.argv = argv


def test_freeze_refuses_overwrite() -> None:
    import freeze_config
    from schema import CASE_RUNTIME

    dest = CASE_RUNTIME / "ov1" / "冻结" / "2099-01-01"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "checksum.txt").write_text("old\n", encoding="utf-8")
    argv = sys.argv[:]
    try:
        sys.argv = ["freeze_config.py", "--date", "2099-01-01", "--case-id", "ov1"]
        try:
            freeze_config.main()
        except SystemExit as e:
            assert "不可覆盖" in str(e)
            return
        raise AssertionError("freeze overwrite must fail")
    finally:
        sys.argv = argv
        import shutil

        shutil.rmtree(CASE_RUNTIME / "ov1", ignore_errors=True)


def test_p0_coverage_fail() -> None:
    plats = [
        {"channel": "app_doubao", "tier": "P0"},
        {"channel": "app_tongyi", "tier": "P0"},
    ]
    qids = ["Q01", "Q02"]
    rows = [{"channel": "app_doubao", "query_id": "Q01", "date": "2026-08-16"}]
    cov = coverage_from(plats, qids, rows, "2026-08-16")
    gap = p0_coverage_gap(cov)
    assert "app_tongyi" in gap
    assert "app_doubao" in gap
    msg = format_p0_coverage_fail(gap)
    assert msg.startswith("覆盖不全: ")
    for ch in gap:
        assert ch in msg
    src = inspect.getsource(main)
    assert "format_p0_coverage_fail" in src
    assert 'r["channel"] for r in incomplete' not in src


def test_main_require_coverage_systemexit() -> None:
    import shutil
    import tempfile

    argv = sys.argv[:]
    tmp = Path(tempfile.mkdtemp(prefix="geo-roll-"))
    old_rt = schema.CASE_RUNTIME
    demo = Path(__file__).resolve().parents[1] / "配置" / "冻结" / "2026-08-16"
    dest = tmp / "ghost" / "冻结" / "2026-08-16"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if demo.is_dir():
        shutil.copytree(demo, dest)
    leftover = Path(__file__).resolve().parents[1] / "案件" / "ghost"
    try:
        schema.CASE_RUNTIME = tmp
        sys.argv = [
            "metrics_rollup.py",
            "--freeze-id",
            "2026-08-16",
            "--date",
            "2099-01-01",
            "--require-coverage",
            "--case-id",
            "ghost",
            "--project-id",
            "P202608-demo",
        ]
        try:
            main()
        except SystemExit as e:
            msg = e.code if isinstance(e.code, str) else str(e)
            assert msg.startswith("覆盖不全:")
            assert "app_" in msg
            return
        raise AssertionError("main() --require-coverage did not SystemExit")
    finally:
        sys.argv = argv
        schema.CASE_RUNTIME = old_rt
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(leftover, ignore_errors=True)


def test_schema_freeze_dir_no_shared_fallback() -> None:
    try:
        schema.freeze_dir("2026-08-16", case_id="no-such-case-xyz")
    except SystemExit as e:
        msg = str(e)
        assert "冻结" in msg
        return
    raise AssertionError("freeze_dir must not fall back to shared 配置/冻结")


def test_holm_on_p0_mention_vector() -> None:
    raw = [0.01, 0.04, 0.20, 0.80]
    adj = holm_adjust(raw)
    assert adj != raw
    assert abs(adj[0] - 0.04) < 1e-12
    assert abs(adj[1] - 0.12) < 1e-12
    rows = [
        {"channel": "app_doubao", "date": "d", "query_set": "core", "city": "c", "product_mode": "standard", "p_mention_p": "0.01"},
        {"channel": "app_tongyi", "date": "d", "query_set": "core", "city": "c", "product_mode": "standard", "p_mention_p": "0.04"},
        {"channel": "app_deepseek", "date": "d", "query_set": "core", "city": "c", "product_mode": "standard", "p_mention_p": "0.20"},
        {"channel": "app_yuanbao", "date": "d", "query_set": "core", "city": "c", "product_mode": "standard", "p_mention_p": "0.80"},
    ]
    apply_p0_mention_holm(rows, {"app_doubao", "app_tongyi", "app_deepseek", "app_yuanbao"})
    holm_vals = [float(r["p_mention_p_holm"]) for r in rows]
    assert holm_vals != raw


def _write_pair(out: Path, ident: dict) -> None:
    did_row = {"channel": "app_x", "metric": "mention", **ident}
    cov_row = {"channel": "app_x", "tier": "P0", "complete": "1", **ident}
    schema.write_csv_atomic(out / "did.csv", list(did_row.keys()), [did_row])
    schema.write_csv_atomic(out / "coverage.csv", list(cov_row.keys()), [cov_row])


def test_partial_rewrite_does_not_clear_invalidation() -> None:
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="geo-ev-"))
    try:
        ident = {
            "case_id": "c1",
            "project_id": "P1",
            "freeze_id": "f1",
            "config_checksum": "abcd",
            "evidence_run_id": "1",
        }
        _write_pair(tmp, ident)
        assert publish_evidence(tmp, ident) is True
        (tmp / "INVALIDATED.txt").write_text(
            "rewind: outputs not current\nepoch=1\n",
            encoding="utf-8",
        )
        old_did = (tmp / "did.csv").read_bytes()
        old_cov = (tmp / "coverage.csv").read_bytes()
        new_ident = dict(ident, evidence_run_id=next_evidence_run_id(tmp))
        assert new_ident["evidence_run_id"] == "2"

        schema.write_csv_atomic(
            tmp / "coverage.csv",
            list({**ident, "channel": "app_x", "tier": "P0", "complete": "1", "evidence_run_id": "2"}.keys()),
            [{"channel": "app_x", "tier": "P0", "complete": "1", **new_ident}],
        )
        assert publish_evidence(tmp, new_ident) is False
        assert (tmp / "INVALIDATED.txt").is_file()

        (tmp / "coverage.csv").write_bytes(old_cov)
        schema.write_csv_atomic(
            tmp / "did.csv",
            list({**ident, "channel": "app_x", "metric": "mention", "evidence_run_id": "2"}.keys()),
            [{"channel": "app_x", "metric": "mention", **new_ident}],
        )
        assert publish_evidence(tmp, new_ident) is False
        assert (tmp / "INVALIDATED.txt").is_file()

        (tmp / "did.csv").write_bytes(old_did)
        _write_pair(tmp, new_ident)
        assert publish_evidence(tmp, new_ident) is True
        assert not (tmp / "INVALIDATED.txt").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_invalidate_archives_and_partial_write_fails() -> None:
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="geo-ev-arc-"))
    try:
        ident = {
            "case_id": "c1",
            "project_id": "P1",
            "freeze_id": "f1",
            "config_checksum": "abcd",
            "evidence_run_id": "1",
        }
        _write_pair(tmp, ident)
        assert publish_evidence(tmp, ident) is True
        invalidate_evidence(tmp)
        assert not (tmp / "did.csv").exists()
        assert not (tmp / "coverage.csv").exists()
        assert (tmp / "失效" / "1" / "did.csv").is_file()
        new_ident = dict(ident, evidence_run_id=next_evidence_run_id(tmp))
        schema.write_csv_atomic(
            tmp / "coverage.csv",
            list({"channel": "app_x", "tier": "P0", "complete": "1", **new_ident}.keys()),
            [{"channel": "app_x", "tier": "P0", "complete": "1", **new_ident}],
        )
        assert publish_evidence(tmp, new_ident) is False
        assert (tmp / "INVALIDATED.txt").is_file()
        schema.write_csv_atomic(
            tmp / "did.csv",
            list({"channel": "app_x", "metric": "mention", **new_ident}.keys()),
            [{"channel": "app_x", "metric": "mention", **new_ident}],
        )
        assert publish_evidence(tmp, new_ident) is True
        assert not (tmp / "INVALIDATED.txt").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_unscored_not_formal()
    test_empty_recommend_not_zero()
    test_sov_both_not_100()
    test_need_equal_weights()
    test_anon_and_leak()
    test_ledger_fields()
    test_cluster_reweight_counts_twice()
    test_did_insufficient_clusters()
    test_did_single_cluster_degenerate()
    test_did_negative_not_confirm()
    test_ledger_filter_by_project()
    test_coverage_ignores_limited()
    test_cli_requires_case_id()
    test_freeze_refuses_overwrite()
    test_p0_coverage_fail()
    test_main_require_coverage_systemexit()
    test_schema_freeze_dir_no_shared_fallback()
    test_holm_on_p0_mention_vector()
    test_partial_rewrite_does_not_clear_invalidation()
    test_invalidate_archives_and_partial_write_fails()
    print("ok")
