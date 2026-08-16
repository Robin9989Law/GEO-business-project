#!/usr/bin/env python3
"""08沟通定向补采：只收干系人/沟通矩阵/决策权/升级/会议决定/汇报层级。不写来源去重总表。"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIT = ROOT / "研究" / "业务流程文献"
WORK = LIT / "_work"
STAGE = "08沟通"

spec = importlib.util.spec_from_file_location(
    "collect_openalex", ROOT / "研究" / "业务流程文献" / "_tools" / "collect_openalex.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)

QUERIES = [
    '"stakeholder analysis" "project management"',
    '"stakeholder salience" project',
    '"stakeholder communication" project',
    '"communication plan" stakeholder project',
    '"communication matrix" stakeholder',
    '"decision rights" project governance',
    'RACI "project management" responsibility',
    '"escalation matrix" project',
    '"escalation procedure" project issue',
    '"decision log" project meeting',
    '"status reporting" "project management"',
    '"virtual team" communication "project performance"',
    '"media richness" "project communication"',
    '"stakeholder engagement" construction project communication',
    '"responsibility assignment matrix" project',
    '"project governance" "decision making" stakeholder',
    '"stakeholder register" project communication',
    '"power interest" stakeholder project',
    '"status meeting" project stakeholder',
    '"project communication" effectiveness stakeholder',
    '"reporting hierarchy" project',
    '"meeting minutes" project decision',
    '"stakeholder mapping" project communication',
    '"communication management plan" project',
]

POS = {
    "stakeholder_analysis": (
        "stakeholder analysis",
        "stakeholder salience",
        "power-interest",
        "power/interest",
        "power interest",
        "stakeholder register",
        "stakeholder mapping",
        "stakeholder matrix",
        "salience model",
    ),
    "comms": (
        "communication matrix",
        "communication plan",
        "stakeholder communication",
        "communication management",
        "project communication",
        "comms plan",
    ),
    "decision_rights": (
        "decision rights",
        "raci",
        "rasci",
        "responsibility assignment",
        "accountable",
        "decision-making authority",
        "decision making authority",
    ),
    "escalation": (
        "escalation matrix",
        "escalation path",
        "escalation procedure",
        "escalate",
        "escalation process",
        "issue escalation",
    ),
    "decision_log": (
        "decision log",
        "decision record",
        "meeting minutes",
        "meeting decision",
        "decision register",
        "action log",
    ),
    "reporting": (
        "status report",
        "status reporting",
        "reporting hierarchy",
        "report level",
        "status meeting",
        "progress report",
        "reporting line",
    ),
    "virtual": (
        "virtual team",
        "media richness",
        "remote team communication",
        "global virtual work",
    ),
}

PROJECT = (
    "project management",
    "construction project",
    "infrastructure project",
    "project communication",
    "project governance",
    "project stakeholder",
    "project team",
    "project performance",
    "program management",
    "project success",
    "project delivery",
)

NEG_TITLE = (
    "higher education",
    "higher-education",
    "pedagogical",
    "classroom",
    "student learning",
    "e-learning",
    "chatgpt",
    "carbon emission",
    "esg disclosure",
    "circular economy",
    "undocumented",
    "migrant worker",
    "serious game",
    "retracted",
    "board effectiveness",
    "climate change adaptation",
    "asbestos",
    "hiv prevention",
    "geoai",
    "civilizational",
    "pidgin",
    "biopsychosocial",
    "teaching learning",
    "faculty engagement",
    "microlearning",
    "blended learning",
    "online, hybrid, and ble",
)

NEG_BLOB = (
    "undergraduate course",
    "k-12",
    "nursing student",
    "curriculum reform",
)


def blob_of(rec: dict) -> str:
    return f"{rec.get('title') or ''} {rec.get('abstract') or ''}".lower()


def cats(blob: str) -> set[str]:
    hit = set()
    for name, terms in POS.items():
        if any(t in blob for t in terms):
            hit.add(name)
    return hit


def is_project(blob: str) -> bool:
    return any(t in blob for t in PROJECT) or ("stakeholder" in blob and "project" in blob)


def on_topic(rec: dict) -> bool:
    title = (rec.get("title") or "").lower()
    blob = blob_of(rec)
    if any(n in title for n in NEG_TITLE):
        return False
    if any(n in blob for n in NEG_BLOB):
        return False
    if not is_project(blob):
        return False
    hit = cats(blob)
    if not hit:
        return False
    # 至少一个沟通/治理主题，不能只靠泛 stakeholder
    strong = hit - set()
    if hit == {"decision_rights"} and "raci" not in blob and "decision rights" not in blob:
        return "responsibility assignment" in blob
    return True


def in_window(rec: dict) -> bool:
    d = rec.get("publication_date") or ""
    year = int(rec.get("year") or 0)
    if d:
        return "2023-08-01" <= d[:10] <= "2026-08-31"
    return year >= 2024  # 无日期的 2023 一律不算（可能早于 8 月）


def rec_from_work(work: dict, query: str) -> dict:
    doi = mod.norm_doi(work.get("doi") or "")
    title = work.get("display_name") or work.get("title") or ""
    abstract = mod.reconstruct_abstract(work.get("abstract_inverted_index"))
    return {
        "openalex_id": work.get("id"),
        "doi": doi,
        "title": title,
        "title_norm": mod.norm_title(title),
        "year": work.get("publication_year") or 0,
        "publication_date": work.get("publication_date") or "",
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count") or 0,
        "authors": mod.authors_of(work),
        "institution": mod.institution_of(work),
        "pdf_url": mod.pdf_url_of(work),
        "oa_status": (work.get("open_access") or {}).get("oa_status"),
        "is_oa": (work.get("open_access") or {}).get("is_oa"),
        "abstract": abstract,
        "query": query,
        "stage": STAGE,
        "landing": ((work.get("primary_location") or {}).get("landing_page_url") or ""),
        "venue": (((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""),
        "topic_cats": sorted(cats(f"{title} {abstract}".lower())),
    }


def load_other_dois() -> set[str]:
    path = LIT / "来源去重总表.csv"
    out = set()
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("stage") != STAGE and row.get("doi"):
                    out.add(mod.norm_doi(row["doi"]))
    return out


def exclude(reason: str, ref: str, query: str = "") -> None:
    path = LIT / STAGE / "排除记录.csv"
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "kind", "query", "reason", "url_or_doi", "date"])
        if not exists or path.stat().st_size == 0:
            w.writeheader()
        w.writerow(
            {
                "stage": STAGE,
                "kind": "paper",
                "query": query,
                "reason": reason,
                "url_or_doi": ref,
                "date": time.strftime("%Y-%m-%d"),
            }
        )


def main() -> None:
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENALEX_API_KEY is not set")
    dest_pdf = LIT / STAGE / "全文" / "pdfs"
    dest_txt = LIT / STAGE / "全文" / "txt"
    dest_pdf.mkdir(parents=True, exist_ok=True)
    dest_txt.mkdir(parents=True, exist_ok=True)
    cand_path = WORK / "08沟通_candidates_strict.json"
    kept_path = WORK / "08沟通_kept.json"

    other = load_other_dois()
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    candidates: list[dict] = []

    # 旧 kept：只保留在窗且在题的
    old = []
    if kept_path.is_file():
        old = json.loads(kept_path.read_text(encoding="utf-8"))
    kept: list[dict] = []
    for rec in old:
        rec.setdefault("publication_date", "")
        rec["topic_cats"] = sorted(cats(blob_of(rec)))
        if not in_window(rec):
            exclude("outside_2023-08_2026-08", rec.get("doi") or rec.get("title") or "", rec.get("query") or "")
            continue
        if not on_topic(rec):
            exclude("off_topic_after_strict_filter", rec.get("doi") or rec.get("title") or "", rec.get("query") or "")
            continue
        kept.append(rec)
        if rec.get("doi"):
            seen_doi.add(mod.norm_doi(rec["doi"]))
        if rec.get("title_norm"):
            seen_title.add(rec["title_norm"])
    print(f"retained from previous kept: {len(kept)}", flush=True)

    for q in QUERIES:
        try:
            works = mod.search_openalex(q, api_key, per_page=50, pages=2, oa_only=True)
        except Exception as exc:  # noqa: BLE001
            print(f"search fail {q}: {exc}", flush=True)
            continue
        for work in works:
            rec = rec_from_work(work, q)
            doi = rec["doi"]
            tn = rec["title_norm"]
            if doi and (doi in seen_doi or doi in other):
                continue
            if tn and tn in seen_title:
                continue
            if not in_window(rec):
                exclude("outside_2023-08_2026-08", doi or rec["title"], q)
                continue
            if not on_topic(rec):
                exclude("title_abstract_not_on_08_topics", doi or rec["title"], q)
                continue
            if doi:
                seen_doi.add(doi)
            if tn:
                seen_title.add(tn)
            candidates.append(rec)
        cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"query done {q!r} cand={len(candidates)}", flush=True)

    # 已有 kept 也并入候选排序池之外
    have = {mod.norm_doi(k.get("doi") or "") for k in kept if k.get("doi")}
    have |= {k.get("title_norm") for k in kept if k.get("title_norm")}

    def rank_key(r: dict) -> tuple:
        ncat = len(r.get("topic_cats") or [])
        return (-ncat, -(int(r.get("cited_by_count") or 0)), -(int(r.get("year") or 0)))

    ranked = sorted(candidates, key=rank_key)
    target = 36
    max_try = 120
    tried = 0
    for rec in ranked:
        if len(kept) >= target:
            break
        if tried >= max_try:
            break
        key_d = mod.norm_doi(rec.get("doi") or "")
        key_t = rec.get("title_norm") or ""
        if (key_d and key_d in have) or (key_t and key_t in have):
            continue
        url = rec.get("pdf_url") or ""
        if not url:
            exclude("no_oa_pdf_url", key_d or rec.get("title") or "", rec.get("query") or "")
            continue
        tried += 1
        fname = mod.slug(rec, tried)
        pdf = dest_pdf / f"{fname}.pdf"
        txt = dest_txt / f"{fname}.txt"
        if not pdf.is_file() or pdf.stat().st_size < 4000:
            ok = mod.download(url, pdf)
            if not ok:
                exclude("pdf_download_failed_or_paywall", url, rec.get("query") or "")
                continue
        if not mod.extract_txt(pdf, txt):
            exclude("fulltext_too_short_or_extract_fail", url, rec.get("query") or "")
            if pdf.exists() and pdf.stat().st_size < 8000:
                pdf.unlink(missing_ok=True)
            continue
        digest = mod.sha256_file(pdf)
        rec = dict(rec)
        rec.update(
            {
                "fulltext_status": "local_pdf_and_txt",
                "pdf_path": str(pdf.relative_to(ROOT)),
                "txt_path": str(txt.relative_to(ROOT)),
                "checksum_sha256": digest,
                "word_count": len(txt.read_text(encoding="utf-8", errors="ignore").split()),
            }
        )
        kept.append(rec)
        have.add(key_d)
        have.add(key_t)
        rec["id"] = f"08-P{len(kept):02d}"
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"kept {len(kept)}/{target}: {rec.get('year')} {rec.get('title')[:90]} cats={rec.get('topic_cats')}", flush=True)

    # 重新编号
    for i, rec in enumerate(kept, 1):
        rec["id"] = f"08-P{i:02d}"
    kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"kept": len(kept), "candidates": len(candidates), "tried": tried}, ensure_ascii=False))


if __name__ == "__main__":
    main()
