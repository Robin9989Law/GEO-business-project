#!/usr/bin/env python3
"""合并各站 _work/*_dedup.csv 到全局去重表。冲突按 DOI / URL / 标题报出。"""

from __future__ import annotations

import csv
from pathlib import Path

LIT = Path(__file__).resolve().parents[1]
FIELDS = ["source_id", "stage", "kind", "doi", "norm_url", "title_norm", "year", "status"]


def rows_of(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if any(r.values())]


def key_of(row: dict) -> str:
    return (row.get("doi") or row.get("norm_url") or row.get("title_norm") or "").strip().lower()


def main() -> None:
    work = LIT / "_work"
    all_rows: list[dict] = []
    seen: dict[str, dict] = {}
    clashes: list[str] = []
    for p in sorted(work.glob("*_dedup.csv")):
        for row in rows_of(p):
            k = key_of(row)
            if k and k in seen and seen[k].get("stage") != row.get("stage"):
                clashes.append(f"{k} :: {seen[k].get('stage')} vs {row.get('stage')}")
                continue
            if k:
                seen[k] = row
            all_rows.append(row)
    out = LIT / "来源去重总表.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in all_rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})
    report = LIT / "_work" / "dedup_clashes.txt"
    report.write_text("\n".join(clashes) + ("\n" if clashes else "none\n"), encoding="utf-8")
    print(f"merged {len(all_rows)} rows, clashes {len(clashes)}")


if __name__ == "__main__":
    main()
