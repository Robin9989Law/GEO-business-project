#!/usr/bin/env python3
"""Recover high-value 08沟通 OA PDFs with browser UA + alternate locations. No global dedup."""
from __future__ import annotations

import importlib.util
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIT = ROOT / "研究" / "业务流程文献"
WORK = LIT / "_work"
STAGE = "08沟通"
dest_pdf = LIT / STAGE / "全文" / "pdfs"
dest_txt = LIT / STAGE / "全文" / "txt"

spec = importlib.util.spec_from_file_location(
    "collect_openalex", ROOT / "研究" / "业务流程文献" / "_tools" / "collect_openalex.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)
strict = importlib.util.spec_from_file_location("collect_08_strict", WORK / "collect_08_strict.py")
smod = importlib.util.module_from_spec(strict)
assert strict.loader
strict.loader.exec_module(smod)

BROWSER = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
MAILTO = os.environ.get("OPENALEX_MAILTO", "geo-research@localhost")
KEY = os.environ.get("OPENALEX_API_KEY", "").strip()

EXTRA_URLS = {
    "10.1016/j.plas.2023.100101": [
        "https://www.econstor.eu/bitstream/10419/339851/1/1886031932.pdf",
        "https://www.sciencedirect.com/science/article/pii/S266672152300045X/pdfft?isDTMRedir=true&download=true",
    ],
    "10.1016/j.compind.2024.104135": [
        "https://www.sciencedirect.com/science/article/pii/S0166361524001182/pdfft?isDTMRedir=true&download=true",
        "https://pure.tue.nl/ws/files/330000000/Digital_Twin_Stakeholder_Communication.pdf",
    ],
    "10.51594/ijmer.v6i7.1330": [
        "https://fepbl.com/index.php/ijmer/article/download/1330/1562",
        "https://fepbl.com/index.php/ijmer/article/view/1330",
    ],
    "10.3390/buildings14092865": [
        "https://www.mdpi.com/2075-5309/14/9/2865/pdf",
        "https://mdpi-res.com/d_attachment/buildings/buildings-14-02865/article_deploy/buildings-14-02865.pdf",
    ],
    "10.3390/buildings15030431": [
        "https://www.mdpi.com/2075-5309/15/3/431/pdf",
    ],
    "10.1007/s11219-024-09665-5": [
        "https://pure.au.dk/ws/files/435229335/Enhancing_big_data_analytics_deployment_Uncovering_stakeholder_dynamics_and_balancing_salience_in_project_roles_Publishers_version_2024.pdf",
        "https://link.springer.com/content/pdf/10.1007/s11219-024-09665-5.pdf",
    ],
    "10.51594/ijmer.v5i12.1535": [
        "https://fepbl.com/index.php/ijmer/article/download/1535/1763",
        "https://fepbl.com/index.php/ijmer/article/view/1535",
    ],
    "10.1057/s41267-025-00775-1": [
        "https://www.econstor.eu/bitstream/10419/330550/1/41267_2025_Article_775.pdf",
    ],
    "10.1108/ijmpb-08-2023-0178": [
        "https://discovery.ucl.ac.uk/10181556/1/Di%20Maddaloni_PDF_Proof.pdf",
    ],
    "10.3390/buildings13092379": [
        "https://www.mdpi.com/2075-5309/13/9/2379/pdf",
    ],
    "10.46729/ijstm.v6i3.1314": [
        "https://ijstm.inarah.co.id/index.php/ijstm/article/download/1314/1119",
    ],
    "10.1109/access.2025.3650467": [
        "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=3650467",
        "https://ieeexplore.ieee.org/ielx8/6287639/10820123/10820123.pdf",
    ],
}


def download_browser(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": BROWSER,
            "Accept": "application/pdf,*/*",
            "Referer": "https://www.google.com/",
        },
    )
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
    except Exception as exc:  # noqa: BLE001
        print(f"  fail {url[:90]} {exc}", flush=True)
        return False


def oa_get(doi: str) -> dict:
    url = (
        "https://api.openalex.org/works/https://doi.org/"
        + urllib.parse.quote(doi)
        + "?select=id,doi,title,display_name,publication_year,publication_date,type,"
        "cited_by_count,authorships,primary_location,open_access,ids,abstract_inverted_index,"
        "best_oa_location,locations"
    )
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}api_key={urllib.parse.quote(KEY)}&mailto={urllib.parse.quote(MAILTO)}"
    req = urllib.request.Request(full, headers={"User-Agent": f"GEO-process-lit/1.0 (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode())


def urls_for(work: dict, doi: str) -> list[str]:
    out = []
    for loc in [work.get("best_oa_location") or {}, work.get("primary_location") or {}]:
        for k in ("pdf_url", "landing_page_url"):
            u = loc.get(k) or ""
            if u:
                out.append(u)
    oa = (work.get("open_access") or {}).get("oa_url") or ""
    if oa:
        out.append(oa)
    for loc in work.get("locations") or []:
        if loc.get("pdf_url"):
            out.append(loc["pdf_url"])
    out.extend(EXTRA_URLS.get(doi, []))
    # mdpi strip version
    extra = []
    for u in out:
        if "mdpi.com" in u and "/pdf?" in u:
            extra.append(u.split("?")[0])
    seen = set()
    clean = []
    for u in out + extra:
        if u and u not in seen:
            seen.add(u)
            clean.append(u)
    return clean


def rec_from(work: dict, query: str) -> dict:
    rec = smod.rec_from_work(work, query)
    rec["publication_date"] = work.get("publication_date") or rec.get("publication_date") or ""
    return rec


def attach(kept: list, rec: dict, pdf: Path, txt: Path) -> None:
    rec = dict(rec)
    rec.update(
        {
            "fulltext_status": "local_pdf_and_txt",
            "pdf_path": str(pdf.relative_to(ROOT)),
            "txt_path": str(txt.relative_to(ROOT)),
            "checksum_sha256": mod.sha256_file(pdf),
            "word_count": len(txt.read_text(encoding="utf-8", errors="ignore").split()),
        }
    )
    kept.append(rec)


def main() -> None:
    dest_pdf.mkdir(parents=True, exist_ok=True)
    dest_txt.mkdir(parents=True, exist_ok=True)
    kept_path = WORK / "08沟通_kept.json"
    kept = json.loads(kept_path.read_text(encoding="utf-8")) if kept_path.is_file() else []
    have = {mod.norm_doi(k.get("doi") or "") for k in kept if k.get("doi")}

    # re-include leftover virtual-work pdf if extracted
    leftover = dest_pdf / "10.1057_s41267_025_00775_1.pdf"
    if leftover.is_file() and "10.1057/s41267-025-00775-1" not in have:
        EXTRA_URLS.setdefault("10.1057/s41267-025-00775-1", [])

    targets = list(EXTRA_URLS)
    # plus remaining high-cite candidates
    cands = json.loads((WORK / "08沟通_candidates_strict.json").read_text(encoding="utf-8"))
    for rec in sorted(cands, key=lambda r: -(r.get("cited_by_count") or 0)):
        d = rec.get("doi") or ""
        if d and d not in have and d not in targets:
            if (rec.get("cited_by_count") or 0) >= 8 or len(rec.get("topic_cats") or []) >= 2:
                targets.append(d)
        if len(targets) >= 70:
            break

    print(f"targets {len(targets)} already {len(kept)}", flush=True)
    for doi in targets:
        if len(kept) >= 40:
            break
        if doi in have:
            continue
        try:
            work = oa_get(doi)
        except Exception as exc:  # noqa: BLE001
            print(f"meta fail {doi} {exc}", flush=True)
            continue
        rec = rec_from(work, "recover")
        if not smod.in_window(rec):
            smod.exclude("outside_window_recover", doi, "recover")
            continue
        # allow known virtual-work review even if project-term thin
        title = (rec.get("title") or "").lower()
        allow = "global virtual work" in title or "digital twin stakeholder" in title
        if not (smod.on_topic(rec) or allow):
            smod.exclude("off_topic_recover", doi, "recover")
            continue
        fname = mod.slug(rec, 0)
        pdf = dest_pdf / f"{fname}.pdf"
        txt = dest_txt / f"{fname}.txt"
        ok = pdf.is_file() and pdf.stat().st_size >= 4000
        if not ok:
            for url in urls_for(work, doi):
                print(f"try {doi} {url[:100]}", flush=True)
                if download_browser(url, pdf):
                    ok = True
                    rec["pdf_url"] = url
                    break
                time.sleep(0.2)
        if not ok:
            smod.exclude("pdf_download_failed_or_paywall", doi, "recover")
            continue
        if not txt.is_file() or not mod.extract_txt(pdf, txt):
            if not mod.extract_txt(pdf, txt):
                smod.exclude("fulltext_too_short_or_extract_fail", doi, "recover")
                continue
        attach(kept, rec, pdf, txt)
        have.add(doi)
        kept[-1]["id"] = f"08-P{len(kept):02d}"
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"kept {len(kept)} {rec.get('year')} {rec.get('title')[:80]}", flush=True)
        time.sleep(0.15)

    for i, rec in enumerate(kept, 1):
        rec["id"] = f"08-P{i:02d}"
    kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"kept": len(kept)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
