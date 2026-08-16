#!/usr/bin/env python3
"""驱动 check_pm_system.main，确认通用模板齐且无客户泄漏。"""

from __future__ import annotations

import check_pm_system


def test_pm_kit_ok() -> None:
    code = check_pm_system.main()
    assert code == 0


def test_measure_scan_covers_operator_asset_freeze_docs() -> None:
    root = check_pm_system.ROOT
    rels = {check_pm_system._measure_rel(root, p) for p in check_pm_system.measure_doc_files(root)}
    assert "流程/03 测量/清单/操作员当日清单.md" in rels
    assert "流程/03 测量/资产库/README.md" in rels
    assert "流程/03 测量/配置/冻结/README.txt" in rels


def test_old_doc_paths_trigger_drift() -> None:
    bad = """
四张表填完，复制一份到 流程/03 测量/配置/冻结/今日日期/。
python3 "流程/03 测量/工具/metrics_rollup.py" --freeze-id 今天 --require-coverage
当日文件进 流程/03 测量/样本/今天/app_*/。
写入 流程/03 测量/台账/samples.csv。
"""
    hits = check_pm_system.drift_hits_in_text(bad)
    assert any("配置/冻结/" in h for h in hits)
    assert any("case-id" in h for h in hits)
    assert any("project-id" in h for h in hits)
    assert any("样本/" in h for h in hits)
    assert any("台账/samples.csv" in h for h in hits)


if __name__ == "__main__":
    test_measure_scan_covers_operator_asset_freeze_docs()
    test_old_doc_paths_trigger_drift()
    test_pm_kit_ok()
    print("ok")
