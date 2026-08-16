#!/usr/bin/env python3
"""05实施控制定向采集：只写本站 kept / 排除记录 / _work/05实施控制_dedup.csv。不改引擎、不写总表。"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_tools"))
import collect_openalex as oa  # noqa: E402

STAGE = "05实施控制"
ROOT = oa.ROOT
LIT = oa.LIT
WORK = oa.WORK
DEST_PDF = LIT / STAGE / "全文" / "pdfs"
DEST_TXT = LIT / STAGE / "全文" / "txt"
KEPT_PATH = WORK / f"{STAGE}_kept.json"
CAND_PATH = WORK / f"{STAGE}_candidates.json"
DEDUP_PATH = WORK / f"{STAGE}_dedup.csv"
EXCL_PATH = LIT / STAGE / "排除记录.csv"

CORE_POS = (
    "earned value",
    "earned schedule",
    "earned duration",
    "change control",
    "integrated change control",
    "change request",
    "change order",
    "holdout group",
    "hold-out group",
    "holdout experiment",
    "hold-out test",
    "online controlled experiment",
    "switchback",
    "issue log",
    "risk register",
    "issue register",
    "management by exception",
    "project control",
    "a/b test",
    "ab test",
    "ab testing",
    "a/b testing",
    "experimentation platform",
    "wait period",
    "waiting period",
    "washout",
    "cooldown period",
    "retest",
    "rework",
)

HARD_NEG = (
    "heart disease",
    "gwas",
    "peptide",
    "cultured meat",
    "powder bed",
    "lung cancer",
    "pollen grain",
    "groundwater",
    "listeria",
    "credit card fraud",
    "fake news",
    "eeg preprocess",
    "lumbar disc",
    "gut microbiome",
    "discrete choice experiment",
    "oral squamous",
    "family-gwas",
    "proteomics",
)

EXTRA_QUERIES = [
    '"earned value management" project control',
    '"earned schedule" project monitoring',
    '"project change control" baseline',
    '"integrated change control" project',
    '"online controlled experiment" holdout',
    '"holdout group" A/B testing experiment',
    '"switchback experiment" causal',
    '"issue log" "risk register" project',
    '"management by exception" earned value',
    "project intervention wait period retest",
    "controlled experiment product metric holdout",
    '"change request" project control process',
]


def blob_of(rec: dict) -> str:
    return f"{rec.get('title','')} {rec.get('abstract','')}".lower()


def on_topic(rec: dict) -> bool:
    blob = blob_of(rec)
    if any(n in blob for n in HARD_NEG):
        return False
    if not any(p in blob for p in CORE_POS):
        return False
    evm = any(
        k in blob
        for k in (
            "earned value",
            "earned schedule",
            "earned duration",
            "change control",
            "change request",
            "project control",
            "issue log",
            "risk register",
            "management by exception",
            "change order",
        )
    )
    exp = any(
        k in blob
        for k in (
            "holdout group",
            "hold-out group",
            "holdout experiment",
            "online controlled experiment",
            "a/b test",
            "ab test",
            "ab testing",
            "switchback",
            "experimentation platform",
            "waiting period",
            "wait period",
            "washout",
        )
    )
    return evm or exp


def in_window(rec: dict) -> bool:
    year = int(rec.get("year") or 0)
    if year < 2023 or year > 2026:
        return False
    # 2023 需 8 月及以后；无日期则年=2023 时保守排除 1–7 月无法判断者，保留 year>=2024
    date = (rec.get("publication_date") or "").strip()
    if date:
        return "2023-08-01" <= date[:10] <= "2026-08-31"
    return year >= 2024 or year == 2023


def exclude(kind: str, query: str, reason: str, ref: str) -> None:
    exists = EXCL_PATH.is_file()
    EXCL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXCL_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "kind", "query", "reason", "url_or_doi", "date"])
        if not exists or EXCL_PATH.stat().st_size == 0:
            w.writeheader()
        w.writerow(
            {
                "stage": STAGE,
                "kind": kind,
                "query": query,
                "reason": reason,
                "url_or_doi": ref,
                "date": time.strftime("%Y-%m-%d"),
            }
        )


def write_dedup(rows: list[dict]) -> None:
    DEDUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEDUP_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source_id", "stage", "kind", "doi", "norm_url", "title_norm", "year", "status"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)


def rec_from_work(work: dict, query: str) -> dict:
    doi = oa.norm_doi(work.get("doi") or "")
    title = work.get("display_name") or work.get("title") or ""
    abstract = oa.reconstruct_abstract(work.get("abstract_inverted_index"))
    return {
        "openalex_id": work.get("id"),
        "doi": doi,
        "title": title,
        "title_norm": oa.norm_title(title),
        "year": work.get("publication_year") or 0,
        "publication_date": work.get("publication_date") or "",
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count") or 0,
        "authors": oa.authors_of(work),
        "institution": oa.institution_of(work),
        "pdf_url": oa.pdf_url_of(work),
        "oa_status": (work.get("open_access") or {}).get("oa_status"),
        "is_oa": (work.get("open_access") or {}).get("is_oa"),
        "abstract": abstract,
        "query": query,
        "stage": STAGE,
        "landing": ((work.get("primary_location") or {}).get("landing_page_url") or ""),
        "venue": (((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""),
    }


def main() -> None:
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENALEX_API_KEY is not set")
    target = int(os.environ.get("OA_TARGET", "36"))
    max_try = int(os.environ.get("OA_MAX_TRY", "100"))
    DEST_PDF.mkdir(parents=True, exist_ok=True)
    DEST_TXT.mkdir(parents=True, exist_ok=True)

    candidates: list[dict] = []
    if CAND_PATH.is_file():
        candidates = json.loads(CAND_PATH.read_text(encoding="utf-8"))

    seen_doi = {oa.norm_doi(c["doi"]) for c in candidates if c.get("doi")}
    seen_title = {c["title_norm"] for c in candidates if c.get("title_norm")}

    for q in EXTRA_QUERIES:
        works = oa.search_openalex(q, api_key, per_page=50, pages=2, oa_only=True)
        for work in works:
            rec = rec_from_work(work, q)
            doi, tn = rec["doi"], rec["title_norm"]
            if not on_topic(rec):
                exclude("paper", q, "title_abstract_not_on_topic", doi or rec["title"])
                continue
            if not in_window(rec):
                exclude("paper", q, "outside_2023-08_2026-08", doi or rec["title"])
                continue
            if doi and doi in seen_doi:
                continue
            if tn and tn in seen_title:
                continue
            if doi:
                seen_doi.add(doi)
            if tn:
                seen_title.add(tn)
            candidates.append(rec)
        CAND_PATH.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"query done {q!r} candidates={len(candidates)}", flush=True)

    topic_pool = [c for c in candidates if on_topic(c) and in_window(c)]
    ranked = sorted(topic_pool, key=lambda r: (-(int(r.get("cited_by_count") or 0)), -(int(r.get("year") or 0))))
    print(f"topic pool {len(topic_pool)}", flush=True)

    kept: list[dict] = []
    if KEPT_PATH.is_file():
        kept = json.loads(KEPT_PATH.read_text(encoding="utf-8"))
    have = {oa.norm_doi(k.get("doi") or "") for k in kept if k.get("doi")}
    have |= {k.get("title_norm") for k in kept if k.get("title_norm")}

    tried = 0
    for rec in ranked:
        if len(kept) >= target:
            break
        if tried >= max_try:
            break
        key_d = oa.norm_doi(rec.get("doi") or "")
        key_t = rec.get("title_norm") or ""
        if (key_d and key_d in have) or (key_t and key_t in have):
            continue
        url = rec.get("pdf_url") or ""
        if not url:
            exclude("paper", rec.get("query") or "", "no_oa_pdf_url", key_d or rec.get("title") or "")
            continue
        tried += 1
        fname = oa.slug(rec, tried)
        pdf = DEST_PDF / f"{fname}.pdf"
        txt = DEST_TXT / f"{fname}.txt"
        if not pdf.is_file() or pdf.stat().st_size < 4000:
            ok = oa.download(url, pdf)
            if not ok:
                exclude("paper", rec.get("query") or "", "pdf_download_failed_or_paywall", url)
                continue
        if not oa.extract_txt(pdf, txt):
            exclude("paper", rec.get("query") or "", "fulltext_too_short_or_extract_fail", url)
            if pdf.exists() and pdf.stat().st_size < 8000:
                pdf.unlink(missing_ok=True)
            continue
        digest = oa.sha256_file(pdf)
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
        rec["id"] = f"05-P{len(kept):02d}"
        KEPT_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[05] kept {len(kept)}/{target}: {rec.get('year')} {rec.get('title')[:90]}", flush=True)

    dedup_rows = []
    for rec in kept:
        dedup_rows.append(
            {
                "source_id": rec.get("id") or "",
                "stage": STAGE,
                "kind": "paper",
                "doi": rec.get("doi") or "",
                "norm_url": rec.get("landing") or rec.get("pdf_url") or "",
                "title_norm": rec.get("title_norm") or "",
                "year": rec.get("year") or "",
                "status": rec.get("fulltext_status") or "fulltext",
            }
        )
    write_dedup(dedup_rows)
    print(json.dumps({"kept": len(kept), "tried": tried, "pool": len(topic_pool)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
