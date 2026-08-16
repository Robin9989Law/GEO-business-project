#!/usr/bin/env python3
"""按冻结词表和 platforms.csv 生成完整操作清单，避免漏 Holdout。"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import CASE_RUNTIME, load_table, require_case_ids


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--task", default="noise")
    p.add_argument("--freeze-id")
    p.add_argument("--case-id", dest="case_id", required=True)
    args = p.parse_args()
    require_case_ids(args.case_id)
    queries = [r for r in load_table("queries.csv", args.freeze_id, case_id=args.case_id) if r.get("active") == "1" and r.get("set") in {"core", "holdout"}]
    plats = [r for r in load_table("platforms.csv", args.freeze_id, case_id=args.case_id) if r.get("active") == "1"]
    run_n = 3 if args.task in {"baseline", "retest"} else 1
    lines = [
        f"# 操作员清单 {args.date} {args.task}",
        "",
        "规则：新建对话；原话不改；只问一句；看完卡片；先存 txt+图。",
        f"冻结：{args.freeze_id or '本案最新冻结'}　案件：{args.case_id}",
        "样本写入本案 样本/ ，不要写共享 样本/",
        "",
    ]
    for plat in plats:
        if not plat["channel"].startswith("app_"):
            continue
        rmax = run_n if plat.get("tier") == "P0" or args.task in {"noise", "weekly"} else 1
        if args.task in {"noise", "weekly"}:
            rmax = 1
        if args.task in {"baseline", "retest"} and plat.get("tier") == "P1":
            rmax = 1
        lines.append(f"## {plat['product']}（{plat['channel']} / {plat.get('tier')}）")
        header = "| query_id | set | need | " + " | ".join(f"r{i}" for i in range(1, rmax + 1)) + " | 上传 |"
        lines += [header, "|" + "---|" * (4 + rmax)]
        for q in queries:
            boxes = " | ".join("□" for _ in range(rmax))
            lines.append(f"| {q['query_id']} | {q['set']} | {q['need_id']} | {boxes} | □ |")
        lines.append("")
    dest_dir = CASE_RUNTIME / args.case_id / "清单"
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"操作员_{args.date}_{args.task}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
