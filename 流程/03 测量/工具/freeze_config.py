#!/usr/bin/env python3
"""把活动配置复制到本案冻结目录。已存在的冻结不可覆盖。"""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import CASE_RUNTIME, CONFIG, config_checksum, require_case_ids

FILES = [
    "queries.csv",
    "aliases.csv",
    "facts.csv",
    "owned_sources.csv",
    "platforms.csv",
    "project.csv",
    "runs_plan.csv",
    "intervention_ledger.csv",
    "对照设计.md",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--case-id", dest="case_id", required=True)
    args = p.parse_args()
    require_case_ids(args.case_id)
    dest = CASE_RUNTIME / args.case_id / "冻结" / args.date
    if dest.is_dir() and (dest / "checksum.txt").is_file():
        raise SystemExit(f"冻结已存在且不可覆盖: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = CONFIG / name
        if src.exists():
            shutil.copy2(src, dest / name)
    checksum = config_checksum(args.date, case_id=args.case_id)
    (dest / "checksum.txt").write_text(checksum + "\n", encoding="utf-8")
    print(f"froze {dest} checksum={checksum}")


if __name__ == "__main__":
    main()
