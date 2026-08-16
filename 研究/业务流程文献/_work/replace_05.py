#!/usr/bin/env python3
"""Replace off-topic 05 kept papers with priority on-topic OA fulltexts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_tools"))
import collect_openalex as oa  # noqa: E402

STAGE = "05实施控制"
ROOT = oa.ROOT
WORK = oa.WORK
DEST_PDF = oa.LIT / STAGE / "全文" / "pdfs"
DEST_TXT = oa.LIT / STAGE / "全文" / "txt"
KEPT_PATH = WORK / f"{STAGE}_kept.json"
CAND_PATH = WORK / f"{STAGE}_candidates.json"
DEDUP_PATH = WORK / f"{STAGE}_dedup.csv"

DROP_DOI = {
    "10.1109/jbhi.2024.3422875",  # eating speed
    "10.3389/fcomm.2023.1187233",  # aphasia
    "10.35923/jes.2024.1.10",  # education change
    "10.1057/s41272-023-00455-5",  # PSS costing
    "10.57111/devt/4.2024.45",  # bank AI risk
    "10.1038/s41598-024-79522-9",  # waste calculator
}

PRIORITY = [
    "10.1080/00031305.2023.2257237",  # OCE statistical challenges
    "10.1016/j.ijresmar.2024.12.004",  # Google/Facebook A/B
    "10.3390/su152216085",  # CCB performance
    "10.3390/buildings14030726",  # variation order
    "10.3390/buildings14030643",  # EAC progress factors
    "10.3390/buildings14123772",  # EVM ML
    "10.1177/87569728231226226",  # EVMS team sport
    "10.1016/j.heliyon.2024.e37810",  # LPS + EVM
    "10.1016/j.heliyon.2024.e27662",  # grey-fuzzy EVA
    "10.1016/j.asej.2023.102472",  # enhanced ESM
    "10.3390/su16209042",  # project controls model
    "10.1108/ijmpb-07-2023-0160",  # sociotechnical EVM
    "10.1080/00207543.2023.2262051",  # ML cost estimates
    "10.3390/machines12120867",  # XGBoost SA
    "10.1016/j.autcon.2025.106426",  # AutoML forecast
    "10.48550/arxiv.2312.15574",  # clustered switchback
    "10.48550/arxiv.2406.06768",  # already may be kept
    "10.48550/arxiv.2410.09027",  # variance reduction
    "10.48550/arxiv.2505.20780",  # dyadic RCT
    "10.32388/kd99xx",  # formal change control
    "10.3390/asi6050075",  # process/product change mgmt
    "10.1155/je/2296387",  # optimized change mgmt
    "10.3390/math13162657",  # causal agile progress
    "10.1080/15623599.2026.2636732",  # risk register IPFS
    "10.48550/arxiv.2501.00119",  # post launch evaluation
]


def write_dedup(kept: list[dict]) -> None:
    import csv

    with DEDUP_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source_id", "stage", "kind", "doi", "norm_url", "title_norm", "year", "status"],
        )
        w.writeheader()
        for rec in kept:
            w.writerow(
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


def try_download(rec: dict, idx: int) -> dict | None:
    url = rec.get("pdf_url") or ""
    if rec.get("doi", "").startswith("10.48550/arxiv."):
        arx = rec["doi"].split("arxiv.")[-1]
        url = f"https://arxiv.org/pdf/{arx}.pdf"
        rec = dict(rec)
        rec["pdf_url"] = url
    if rec.get("doi") == "10.48550/arxiv.2312.15574":
        rec = dict(rec)
        rec["pdf_url"] = "https://arxiv.org/pdf/2312.15574.pdf"
        url = rec["pdf_url"]
    if rec.get("doi") == "10.48550/arxiv.2410.09027":
        rec = dict(rec)
        rec["pdf_url"] = "https://arxiv.org/pdf/2410.09027.pdf"
        url = rec["pdf_url"]
    if rec.get("doi") == "10.48550/arxiv.2505.20780":
        rec = dict(rec)
        rec["pdf_url"] = "https://arxiv.org/pdf/2505.20780.pdf"
        url = rec["pdf_url"]
    if rec.get("doi") == "10.48550/arxiv.2501.00119":
        rec = dict(rec)
        rec["pdf_url"] = "https://arxiv.org/pdf/2501.00119.pdf"
        url = rec["pdf_url"]
    if not url:
        return None
    fname = oa.slug(rec, idx)
    pdf = DEST_PDF / f"{fname}.pdf"
    txt = DEST_TXT / f"{fname}.txt"
    if not pdf.is_file() or pdf.stat().st_size < 4000:
        if not oa.download(url, pdf):
            print("FAIL dl", rec.get("doi"), url[:80], flush=True)
            return None
    if not oa.extract_txt(pdf, txt):
        print("FAIL txt", rec.get("doi"), flush=True)
        return None
    rec = dict(rec)
    rec.update(
        {
            "fulltext_status": "local_pdf_and_txt",
            "pdf_path": str(pdf.relative_to(ROOT)),
            "txt_path": str(txt.relative_to(ROOT)),
            "checksum_sha256": oa.sha256_file(pdf),
            "word_count": len(txt.read_text(encoding="utf-8", errors="ignore").split()),
        }
    )
    return rec


def main() -> None:
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    kept = json.loads(KEPT_PATH.read_text(encoding="utf-8"))
    cands = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    by_doi = {oa.norm_doi(c.get("doi") or ""): c for c in cands if c.get("doi")}

    # drop off-topic files
    new_kept = []
    for rec in kept:
        doi = oa.norm_doi(rec.get("doi") or "")
        if doi in DROP_DOI:
            for key in ("pdf_path", "txt_path"):
                p = rec.get(key)
                if p:
                    fp = ROOT / p
                    if fp.is_file():
                        fp.unlink()
                        print("rm", p)
            print("drop", doi, rec.get("title", "")[:70])
            continue
        new_kept.append(rec)

    have = {oa.norm_doi(k.get("doi") or "") for k in new_kept}
    have |= {k.get("title_norm") for k in new_kept}

    # fetch missing priority metadata from OpenAlex if needed
    for doi in PRIORITY:
        if oa.norm_doi(doi) in by_doi:
            continue
        if doi.startswith("10.48550/arxiv."):
            continue
        url = f"https://api.openalex.org/works/https://doi.org/{doi}?mailto={oa.MAILTO}"
        try:
            work = oa.api_get(url, api_key)
        except Exception as exc:  # noqa: BLE001
            print("meta fail", doi, exc)
            continue
        rec = {
            "openalex_id": work.get("id"),
            "doi": oa.norm_doi(work.get("doi") or doi),
            "title": work.get("display_name") or work.get("title") or "",
            "title_norm": oa.norm_title(work.get("display_name") or work.get("title") or ""),
            "year": work.get("publication_year") or 0,
            "publication_date": work.get("publication_date") or "",
            "type": work.get("type"),
            "cited_by_count": work.get("cited_by_count") or 0,
            "authors": oa.authors_of(work),
            "institution": oa.institution_of(work),
            "pdf_url": oa.pdf_url_of(work),
            "oa_status": (work.get("open_access") or {}).get("oa_status"),
            "is_oa": (work.get("open_access") or {}).get("is_oa"),
            "abstract": oa.reconstruct_abstract(work.get("abstract_inverted_index")),
            "query": "priority_seed",
            "stage": STAGE,
            "landing": ((work.get("primary_location") or {}).get("landing_page_url") or ""),
            "venue": (((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""),
        }
        by_doi[rec["doi"]] = rec
        cands.append(rec)
        print("seeded", rec["doi"], rec["title"][:70], rec.get("pdf_url", "")[:60])

    CAND_PATH.write_text(json.dumps(cands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    idx = 200
    for doi in PRIORITY:
        if len(new_kept) >= 36:
            break
        key = oa.norm_doi(doi)
        if key in have:
            continue
        rec = by_doi.get(key)
        if rec is None:
            # synthesize arxiv
            if doi.startswith("10.48550/arxiv."):
                arx = doi.split("arxiv.")[-1]
                rec = {
                    "doi": doi,
                    "title": arx,
                    "title_norm": oa.norm_title(arx),
                    "year": int("20" + arx[:2]),
                    "pdf_url": f"https://arxiv.org/pdf/{arx}.pdf",
                    "landing": f"https://arxiv.org/abs/{arx}",
                    "query": "priority_arxiv",
                    "stage": STAGE,
                    "abstract": "",
                    "authors": [],
                    "institution": "arXiv",
                    "cited_by_count": 0,
                    "type": "preprint",
                    "oa_status": "green",
                    "is_oa": True,
                }
            else:
                print("missing cand", doi)
                continue
        idx += 1
        got = try_download(rec, idx)
        if not got:
            continue
        new_kept.append(got)
        have.add(key)
        have.add(got.get("title_norm"))
        print("ADD", got.get("year"), got.get("doi"), got.get("title", "")[:80], flush=True)

    # renumber
    for i, rec in enumerate(new_kept, 1):
        rec["id"] = f"05-P{i:02d}"
    KEPT_PATH.write_text(json.dumps(new_kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_dedup(new_kept)
    print("kept", len(new_kept))
    for rec in new_kept:
        print(rec["id"], rec.get("year"), rec.get("doi"), (rec.get("title") or "")[:70])


if __name__ == "__main__":
    main()
