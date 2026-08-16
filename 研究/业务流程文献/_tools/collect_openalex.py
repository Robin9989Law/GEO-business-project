#!/usr/bin/env python3
"""OpenAlex OA 检索与全文落盘。密钥只读环境变量 OPENALEX_API_KEY，不写仓库。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIT = ROOT / "研究" / "业务流程文献"
WORK = LIT / "_work"
MAILTO = os.environ.get("OPENALEX_MAILTO", "geo-research@localhost")
UA = f"GEO-process-lit/1.0 (mailto:{MAILTO})"
SELECT = (
    "id,doi,title,display_name,publication_year,publication_date,type,"
    "cited_by_count,authorships,primary_location,open_access,ids,abstract_inverted_index"
)

MUST_TERMS = {
    "01洽谈": (
        "sales", "selling", "salesperson", "salesperson", "b2b", "discovery",
        "qualification", "consultative", "opportunity", "buyer", "seller",
        "solution selling", "adaptive selling", "lead qualification",
    ),
    "02需求": (
        "requirement", "elicitation", "traceability", "acceptance criteria",
        "specification", "software engineering", "goal-oriented", "napire",
    ),
    "07预算": (
        "effort estimation", "cost estimation", "planning fallacy", "cocomo",
        "planning poker", "contingency", "reference class", "overrun",
        "expert judgment", "analogy",
    ),
    "08沟通": (
        "stakeholder", "communication", "raci", "escalation", "virtual team",
        "media richness", "status report", "decision rights", "engagement",
    ),
    "04计划": (
        "work breakdown", "wbs", "critical path", "critical chain", "schedule",
        "rolling wave", "design structure matrix", "milestone", "baseline",
    ),
    "05实施控制": (
        "earned value", "earned schedule", "change control", "holdout",
        "experiment", "a/b", "rework", "project control", "risk management",
    ),
    "06交付": (
        "acceptance", "verification", "validation", "configuration management",
        "traceability", "stage-gate", "inspection", "handover", "uat",
        "release",
    ),
    "09收尾": (
        "lessons learned", "closeout", "close-out", "post-project",
        "benefits realization", "organizational learning", "project success",
        "knowledge transfer", "appraisal",
    ),
}

STAGES = {
    "01洽谈": {
        "code": "01",
        "queries": [
            '"sales discovery" interview B2B qualification',
            '"opportunity qualification" BANT MEDDIC selling',
            '"consultative selling" needs assessment disqualification',
            '"sales ethics" overselling customer promises',
            '"solution selling" product-line selection B2B',
            '"lead qualification" intake interview salesperson',
            '"adaptive selling" customer discovery conversation',
            "professional selling transformation industrial marketing",
        ],
        "concepts": [],
    },
    "02需求": {
        "code": "02",
        "queries": [
            '"requirements elicitation" techniques empirical software',
            '"requirements traceability" acceptance criteria',
            '"requirements engineering" change management validation',
            "agile requirements engineering systematic review",
            '"goal-oriented requirements" KAOS i-star',
            '"requirements ambiguity" specification quality',
            '"acceptance criteria" software requirements testing',
            "NaPiRE requirements engineering empirical",
        ],
    },
    "07预算": {
        "code": "07",
        "queries": [
            '"software effort estimation" systematic review',
            '"expert judgment" effort estimation software',
            '"planning fallacy" project cost overrun',
            "COCOMO software cost estimation",
            '"agile effort estimation" planning poker',
            '"reference class forecasting" project budget contingency',
            '"analogy based estimation" software effort',
            "project cost contingency reserve risk",
        ],
    },
    "08沟通": {
        "code": "08",
        "queries": [
            '"stakeholder theory" project management salience',
            '"project communication" stakeholder engagement',
            '"virtual team" communication project performance',
            '"media richness" project communication',
            '"stakeholder analysis" construction project',
            "project status reporting escalation decision rights",
            '"RACI" responsibility assignment project',
            "project meeting effectiveness decision log",
        ],
    },
    "04计划": {
        "code": "04",
        "queries": [
            '"work breakdown structure" project planning',
            '"critical path" project scheduling baseline',
            '"critical chain" project management schedule',
            '"rolling wave planning" product-based planning',
            '"design structure matrix" dependency project',
            "project milestone planning WBS empirical",
            "earned value schedule performance index planning",
            "project schedule contingency buffer",
        ],
    },
    "05实施控制": {
        "code": "05",
        "queries": [
            '"earned value management" project control',
            '"project change control" rework',
            '"online controlled experiment" holdout A/B testing',
            '"project risk management" issue log',
            '"management by exception" project control',
            "project intervention change order wait period",
            '"earned schedule" project monitoring',
            "controlled experiment product metric holdout",
        ],
    },
    "06交付": {
        "code": "06",
        "queries": [
            '"user acceptance testing" software delivery',
            '"verification and validation" software acceptance',
            '"configuration management" software release checklist',
            '"requirements to test" traceability acceptance',
            '"stage-gate" new product development review',
            "software inspection Fagan review handover",
            '"customer acceptance" project deliverable',
            "software release integrity checksum configuration",
        ],
    },
    "09收尾": {
        "code": "09",
        "queries": [
            '"lessons learned" project closeout knowledge',
            '"project close-out" post-project review',
            '"project success" iron triangle benefits realization',
            '"organizational learning" project-based organization',
            '"post-project appraisal" knowledge transfer',
            "project archive records close phase",
            '"benefits realization" project management',
            "project lessons learned failure knowledge management",
        ],
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", "", t)
    return t


def norm_doi(doi: str) -> str:
    d = (doi or "").strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d.lower()


def reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def authors_of(work: dict) -> list[str]:
    out = []
    for a in work.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if name:
            out.append(name)
    return out


def institution_of(work: dict) -> str:
    for a in work.get("authorships") or []:
        insts = a.get("institutions") or []
        if insts:
            name = (insts[0].get("display_name") or "").strip()
            if name:
                return name
    return ""


def pdf_url_of(work: dict) -> str:
    oa = work.get("open_access") or {}
    url = oa.get("oa_url") or ""
    loc = work.get("primary_location") or {}
    pdf = loc.get("pdf_url") or ""
    if pdf:
        return pdf
    if url and url.lower().endswith(".pdf"):
        return url
    return url or loc.get("landing_page_url") or ""


def api_get(url: str, api_key: str, retries: int = 4) -> dict:
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}api_key={urllib.parse.quote(api_key)}"
    req = urllib.request.Request(full, headers={"User-Agent": UA, "Accept": "application/json"})
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"OpenAlex GET failed {url}: {last}")


def relevant(stage: str, title: str, abstract: str) -> bool:
    blob = f"{title} {abstract}".lower()
    terms = MUST_TERMS.get(stage) or ()
    return any(t in blob for t in terms)


def search_openalex(query: str, api_key: str, per_page: int = 50, pages: int = 2, oa_only: bool = True) -> list[dict]:
    filt = ["type:article|review|preprint"]
    if oa_only:
        filt.append("is_oa:true")
    # 重点近三年（2023-08 至今）；经典另走 --allow-classic 种子，不占主检索。
    start = os.environ.get("OPENALEX_FROM", "2023-08-01")
    filt.append(f"from_publication_date:{start}")
    q = urllib.parse.urlencode(
        {
            "search": query,
            "filter": ",".join(filt),
            "sort": "relevance_score:desc",
            "per_page": str(per_page),
            "select": SELECT,
            "mailto": MAILTO,
        }
    )
    out = []
    for page in range(1, pages + 1):
        url = f"https://api.openalex.org/works?{q}&page={page}"
        data = api_get(url, api_key)
        out.extend(data.get("results") or [])
        time.sleep(0.12)
    return out


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
        if len(data) < 4000:
            return False
        if "pdf" not in ctype and not data.startswith(b"%PDF"):
            return False
        dest.write_bytes(data)
        return dest.stat().st_size >= 4000
    except Exception:  # noqa: BLE001
        return False


def extract_txt(pdf: Path, txt: Path) -> bool:
    txt.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["pdftotext", "-layout", str(pdf), str(txt)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except Exception:  # noqa: BLE001
        return False
    if not txt.is_file():
        return False
    words = len(txt.read_text(encoding="utf-8", errors="ignore").split())
    return words >= 800


def load_dedup() -> dict[str, dict]:
    path = LIT / "来源去重总表.csv"
    rows = {}
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                key = (row.get("doi") or row.get("norm_url") or row.get("title_norm") or "").strip()
                if key:
                    rows[key] = row
    return rows


def append_dedup(row: dict) -> None:
    path = LIT / "来源去重总表.csv"
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source_id", "stage", "kind", "doi", "norm_url", "title_norm", "year", "status"],
        )
        if not exists:
            w.writeheader()
        w.writerow(row)


def exclude(stage: str, kind: str, query: str, reason: str, ref: str) -> None:
    path = WORK / "排除草稿.csv"
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "kind", "query", "reason", "url_or_doi", "date"])
        if not exists:
            w.writeheader()
        w.writerow(
            {
                "stage": stage,
                "kind": kind,
                "query": query,
                "reason": reason,
                "url_or_doi": ref,
                "date": time.strftime("%Y-%m-%d"),
            }
        )


def slug(work: dict, idx: int) -> str:
    doi = norm_doi(work.get("doi") or "")
    if doi:
        return re.sub(r"[^a-z0-9.]+", "_", doi.replace("10.", "10."))[:80]
    return f"noid_{idx:04d}"


def collect_stage(stage: str, api_key: str, target: int, max_try: int) -> dict:
    spec = STAGES[stage]
    dest_pdf = LIT / stage / "全文" / "pdfs"
    dest_txt = LIT / stage / "全文" / "txt"
    dest_pdf.mkdir(parents=True, exist_ok=True)
    dest_txt.mkdir(parents=True, exist_ok=True)
    cand_path = WORK / f"{stage}_candidates.json"
    kept_path = WORK / f"{stage}_kept.json"
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    dedup = load_dedup()
    candidates: list[dict] = []
    if cand_path.is_file():
        candidates = json.loads(cand_path.read_text(encoding="utf-8"))
        for c in candidates:
            if c.get("doi"):
                seen_doi.add(norm_doi(c["doi"]))
            if c.get("title_norm"):
                seen_title.add(c["title_norm"])

    for q in spec["queries"]:
        works = search_openalex(q, api_key, per_page=50, pages=2, oa_only=True)
        for work in works:
            doi = norm_doi(work.get("doi") or "")
            title = work.get("display_name") or work.get("title") or ""
            abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
            tn = norm_title(title)
            if not relevant(stage, title, abstract):
                exclude(stage, "paper", q, "title_abstract_not_on_topic", doi or title)
                continue
            if doi and (doi in seen_doi or doi in dedup):
                continue
            if tn and (tn in seen_title or tn in dedup):
                continue
            year = work.get("publication_year") or 0
            rec = {
                "openalex_id": work.get("id"),
                "doi": doi,
                "title": title,
                "title_norm": tn,
                "year": year,
                "type": work.get("type"),
                "cited_by_count": work.get("cited_by_count") or 0,
                "authors": authors_of(work),
                "institution": institution_of(work),
                "pdf_url": pdf_url_of(work),
                "oa_status": (work.get("open_access") or {}).get("oa_status"),
                "is_oa": (work.get("open_access") or {}).get("is_oa"),
                "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                "query": q,
                "stage": stage,
                "landing": ((work.get("primary_location") or {}).get("landing_page_url") or ""),
                "venue": (((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""),
            }
            rec["abstract"] = abstract
            if doi:
                seen_doi.add(doi)
            if tn:
                seen_title.add(tn)
            candidates.append(rec)
        cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    kept = []
    if kept_path.is_file():
        kept = json.loads(kept_path.read_text(encoding="utf-8"))
    have = {norm_doi(k.get("doi") or "") for k in kept if k.get("doi")}
    have |= {k.get("title_norm") for k in kept if k.get("title_norm")}

    min_year = int(os.environ.get("OPENALEX_MIN_YEAR", "2023"))
    ranked = sorted(
        candidates,
        key=lambda r: (
            0 if int(r.get("year") or 0) >= min_year else 1,
            -(int(r.get("cited_by_count") or 0)),
        ),
    )
    tried = 0
    for rec in ranked:
        if len(kept) >= target:
            break
        if tried >= max_try:
            break
        if int(rec.get("year") or 0) < min_year:
            exclude(stage, "paper", rec.get("query") or "", f"older_than_{min_year}", rec.get("doi") or rec.get("title") or "")
            continue
        key_d = norm_doi(rec.get("doi") or "")
        key_t = rec.get("title_norm") or ""
        if (key_d and key_d in have) or (key_t and key_t in have):
            continue
        url = rec.get("pdf_url") or ""
        if not url:
            exclude(stage, "paper", rec.get("query") or "", "no_oa_pdf_url", key_d or rec.get("title") or "")
            continue
        tried += 1
        fname = slug(rec, tried)
        pdf = dest_pdf / f"{fname}.pdf"
        txt = dest_txt / f"{fname}.txt"
        if not pdf.is_file() or pdf.stat().st_size < 4000:
            ok = download(url, pdf)
            if not ok:
                exclude(stage, "paper", rec.get("query") or "", "pdf_download_failed_or_paywall", url)
                continue
        if not extract_txt(pdf, txt):
            exclude(stage, "paper", rec.get("query") or "", "fulltext_too_short_or_extract_fail", url)
            if pdf.exists() and pdf.stat().st_size < 8000:
                pdf.unlink(missing_ok=True)
            continue
        digest = sha256_file(pdf)
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
        sid = f"{spec['code']}-P{len(kept):02d}"
        rec["id"] = sid
        append_dedup(
            {
                "source_id": sid,
                "stage": stage,
                "kind": "paper",
                "doi": key_d,
                "norm_url": rec.get("landing") or url,
                "title_norm": key_t,
                "year": rec.get("year") or "",
                "status": "fulltext",
            }
        )
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[{stage}] kept {len(kept)}/{target}: {rec.get('year')} {rec.get('title')[:80]}", flush=True)

    return {"stage": stage, "candidates": len(candidates), "kept": len(kept), "tried": tried}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append", choices=sorted(STAGES), help="repeatable")
    ap.add_argument("--target", type=int, default=36)
    ap.add_argument("--max-try", type=int, default=90)
    args = ap.parse_args()
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENALEX_API_KEY is not set")
    WORK.mkdir(parents=True, exist_ok=True)
    stages = args.stage or list(STAGES)
    summary = []
    for stage in stages:
        print(f"=== {stage} ===", flush=True)
        summary.append(collect_stage(stage, api_key, args.target, args.max_try))
    (WORK / "collect_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
