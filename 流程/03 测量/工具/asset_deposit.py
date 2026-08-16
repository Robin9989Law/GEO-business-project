#!/usr/bin/env python3
"""脱敏沉淀。按复合键 upsert，空面板不记成功，client_only / 自有域 fail-closed。"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import CONFIG, MEASURE, ROOT, case_ledger, case_out_dir, freeze_dir, load_table, read_csv, require_case_ids, write_csv_atomic

LEDGER = MEASURE / "台账" / "samples.csv"
CALIB = MEASURE / "出数" / "calibration.csv"
ASSET = MEASURE / "资产库"


def anon_project(project_id: str) -> str:
    if not project_id:
        return ""
    return hashlib.sha256(f"geo-asset|{project_id}".encode()).hexdigest()[:12]


def self_surfaces(freeze_id: str | None = None, case_id: str | None = None) -> set[str]:
    return {
        r["surface"].strip()
        for r in load_table("aliases.csv", freeze_id, case_id=case_id)
        if r.get("type") == "self" and r.get("surface")
    }


def owned_hosts(freeze_id: str | None = None, case_id: str | None = None) -> set[str]:
    hosts = set()
    for r in load_table("owned_sources.csv", freeze_id, case_id=case_id):
        pat = (r.get("pattern") or "").lower()
        if not pat:
            continue
        if "://" in pat:
            hosts.add(urlparse(pat).netloc.lower().removeprefix("www."))
        else:
            hosts.add(pat.replace("www.", ""))
    return {h for h in hosts if h}


def redact(text: str, banned: set[str]) -> str:
    out = text or ""
    for s in sorted(banned, key=len, reverse=True):
        if s:
            out = out.replace(s, "[品牌]")
    return out


def domains_from(source_raw: str) -> list[str]:
    found = []
    for token in re.split(r"[;\s]+", source_raw or ""):
        token = token.strip()
        if not token or token == "unknown":
            continue
        if "://" in token:
            host = urlparse(token).netloc.lower().removeprefix("www.")
            if host:
                found.append(host)
        elif "." in token and " " not in token:
            found.append(token.lower().removeprefix("www."))
    return found


def upsert_rows(path: Path, fields: list[str], rows: list[dict], key_fields: list[str]) -> int:
    existing = read_csv(path)
    index = {tuple(r.get(k, "") for k in key_fields): r for r in existing}
    for r in rows:
        index[tuple(r.get(k, "") for k in key_fields)] = {k: r.get(k, "") for k in fields}
    write_csv_atomic(path, fields, list(index.values()))
    return len(rows)


def leak_scan(text: str, banned: set[str], owned: set[str]) -> list[str]:
    hits = []
    for s in banned:
        if s and s in (text or ""):
            hits.append(f"brand:{s}")
    for h in owned:
        if h and h in (text or "").lower():
            hits.append(f"owned:{h}")
    if re.search(r"1[3-9]\d{9}", text or ""):
        hits.append("phone")
    return hits


def deposit_needs(qmap: dict[str, dict], banned: set[str], proj: dict) -> int:
    fields = [
        "vertical",
        "need_id",
        "paraphrase_id",
        "kumar_cat",
        "intent",
        "style",
        "persona",
        "locale_pattern",
        "text_redacted",
        "set",
    ]
    rows = []
    city = proj.get("city", "")
    for q in qmap.values():
        if q.get("branded") == "1" or q.get("asset_class") == "client_only":
            continue
        text = redact(q.get("text", ""), banned)
        if city:
            text = text.replace(city, "{city}")
        loc = q.get("locale", "")
        rows.append(
            {
                "vertical": proj.get("vertical", ""),
                "need_id": q.get("need_id", ""),
                "paraphrase_id": q.get("paraphrase_id", ""),
                "kumar_cat": q.get("kumar_cat", ""),
                "intent": q.get("intent", ""),
                "style": q.get("style", ""),
                "persona": q.get("persona", ""),
                "locale_pattern": loc.replace(city, "{city}") if city else loc,
                "text_redacted": text,
                "set": q.get("set", ""),
            }
        )
    return upsert_rows(
        ASSET / "词表池" / "needs.csv",
        fields,
        rows,
        ["vertical", "need_id", "paraphrase_id", "style", "text_redacted"],
    )


def deposit_panel(day: str, qmap: dict[str, dict], proj: dict) -> list[dict]:
    fields = [
        "date",
        "project_anon",
        "vertical",
        "city",
        "platform",
        "channel",
        "need_id",
        "style",
        "persona",
        "query_set",
        "n_valid",
        "n_competitor",
        "n_recommend",
        "n_search_on",
        "n_limited",
    ]
    buckets: dict[tuple, dict] = {}
    limited: dict[tuple, int] = {}
    for r in read_csv(LEDGER):
        q = qmap.get(r.get("query_id", ""), {})
        if q.get("branded") == "1" or q.get("asset_class") == "client_only":
            continue
        if r.get("date") != day:
            continue
        key = (
            r.get("date", ""),
            r.get("platform", ""),
            r.get("channel", ""),
            q.get("need_id", ""),
            q.get("style", ""),
            q.get("persona", ""),
            r.get("query_set", ""),
        )
        if r.get("limited") == "1":
            limited[key] = limited.get(key, 0) + 1
            continue
        if r.get("mention", "") == "":
            continue
        b = buckets.setdefault(key, {"n_valid": 0, "n_competitor": 0, "n_recommend": 0, "n_search_on": 0})
        b["n_valid"] += 1
        if r.get("competitor_hit") == "1":
            b["n_competitor"] += 1
        if (r.get("recommend") or "0") in {"1", "2"}:
            b["n_recommend"] += 1
        if r.get("search_triggered") == "1":
            b["n_search_on"] += 1
    rows = []
    anon = anon_project(proj.get("project_id", ""))
    for key, b in sorted(buckets.items()):
        rows.append(
            {
                "date": key[0],
                "project_anon": anon,
                "vertical": proj.get("vertical", ""),
                "city": proj.get("city", ""),
                "platform": key[1],
                "channel": key[2],
                "need_id": key[3],
                "style": key[4],
                "persona": key[5],
                "query_set": key[6],
                "n_valid": str(b["n_valid"]),
                "n_competitor": str(b["n_competitor"]),
                "n_recommend": str(b["n_recommend"]),
                "n_search_on": str(b["n_search_on"]),
                "n_limited": str(limited.get(key, 0)),
            }
        )
    if rows:
        upsert_rows(ASSET / "面板" / "market_panel.csv", fields, rows, ["date", "project_anon", "channel", "need_id", "style", "query_set"])
    return rows


def deposit_domains(day: str, qmap: dict[str, dict], proj: dict, owned: set[str]) -> list[dict]:
    fields = ["date", "vertical", "city", "platform", "channel", "domain", "n"]
    ctr: Counter[tuple] = Counter()
    for r in read_csv(LEDGER):
        q = qmap.get(r.get("query_id", ""), {})
        if q.get("branded") == "1" or q.get("asset_class") == "client_only":
            continue
        if r.get("date") != day or r.get("limited") == "1":
            continue
        for d in domains_from(r.get("source_raw", "")):
            if d in owned or any(d.endswith(h) for h in owned):
                continue
            ctr[(r.get("date", ""), r.get("platform", ""), r.get("channel", ""), d)] += 1
    rows = [
        {
            "date": k[0],
            "vertical": proj.get("vertical", ""),
            "city": proj.get("city", ""),
            "platform": k[1],
            "channel": k[2],
            "domain": k[3],
            "n": str(n),
        }
        for k, n in sorted(ctr.items())
    ]
    if rows:
        upsert_rows(ASSET / "来源域" / "domains.csv", fields, rows, ["date", "channel", "domain"])
    return rows


def deposit_calib(day: str, proj: dict) -> list[dict]:
    fields = [
        "date",
        "project_anon",
        "vertical",
        "app_channel",
        "api_channel",
        "n_app",
        "n_api",
        "app_p_mention",
        "api_p_mention",
        "gap",
        "app_cite_n",
        "api_cite_n",
        "cite_domain_jaccard",
        "action",
    ]
    anon = anon_project(proj.get("project_id", ""))
    rows = []
    for r in read_csv(CALIB):
        if r.get("date") != day:
            continue
        rows.append(
            {
                "date": r.get("date", ""),
                "project_anon": anon,
                "vertical": proj.get("vertical", ""),
                "app_channel": r.get("app_channel", ""),
                "api_channel": r.get("api_channel", ""),
                "n_app": r.get("n_app", ""),
                "n_api": r.get("n_api", ""),
                "app_p_mention": r.get("app_p_mention", ""),
                "api_p_mention": r.get("api_p_mention", ""),
                "gap": r.get("gap", ""),
                "app_cite_n": r.get("app_cite_n", ""),
                "api_cite_n": r.get("api_cite_n", ""),
                "cite_domain_jaccard": r.get("cite_domain_jaccard", ""),
                "action": r.get("action", ""),
            }
        )
    if rows:
        upsert_rows(ASSET / "校准史" / "calibration_long.csv", fields, rows, ["date", "project_anon", "app_channel"])
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="GEO 资产沉淀（脱敏 upsert）")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--freeze-id")
    p.add_argument("--project-id", dest="project_id", required=True)
    p.add_argument("--case-id", dest="case_id", required=True)
    args = p.parse_args()
    require_case_ids(args.case_id, args.project_id)
    global LEDGER, CALIB
    LEDGER = case_ledger(args.case_id)
    CALIB = case_out_dir(args.case_id) / "calibration.csv"
    proj_rows = load_table("project.csv", args.freeze_id, case_id=args.case_id)
    if not proj_rows:
        raise SystemExit("缺少 project.csv")
    proj = proj_rows[0]
    if args.project_id and proj.get("project_id") and proj.get("project_id") != args.project_id:
        raise SystemExit("project_id 与冻结不一致")
    qmap = {r["query_id"]: r for r in load_table("queries.csv", args.freeze_id, case_id=args.case_id)}
    banned = self_surfaces(args.freeze_id, args.case_id)
    owned = owned_hosts(args.freeze_id, args.case_id)
    n_needs = deposit_needs(qmap, banned, proj)
    panel = deposit_panel(args.date, qmap, proj)
    domains = deposit_domains(args.date, qmap, proj, owned)
    calib = deposit_calib(args.date, proj)
    blob = ""
    for path in (ASSET / "词表池" / "needs.csv", ASSET / "面板" / "market_panel.csv"):
        if path.exists():
            blob += path.read_text(encoding="utf-8", errors="replace")
    leaks = leak_scan(blob, banned, owned)
    if leaks:
        raise SystemExit("资产泄漏扫描失败: " + ",".join(leaks[:8]))
    status = "ok" if panel or domains or calib else "needs_only"
    upsert_rows(
        ASSET / "登记" / "deposits.csv",
        ["date", "project_anon", "needs", "panel_slices", "domains", "calib_rows", "status"],
        [
            {
                "date": args.date,
                "project_anon": anon_project(proj.get("project_id", "")),
                "needs": str(n_needs),
                "panel_slices": str(len(panel)),
                "domains": str(len(domains)),
                "calib_rows": str(len(calib)),
                "status": status,
            }
        ],
        ["date", "project_anon"],
    )
    print(f"deposited needs={n_needs} panel={len(panel)} domains={len(domains)} calib={len(calib)} status={status}")


if __name__ == "__main__":
    main()
