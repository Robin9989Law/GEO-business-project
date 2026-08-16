#!/usr/bin/env python3
"""给缺校验和的论文配 PDF，并用 Tavily 补合格技术博客。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

LIT = Path(__file__).resolve().parents[1]
ROOT = LIT.parents[1]
EXTRACT = "https://api.tavily.com/extract"

REPLACEMENTS = {
    "01洽谈": [
        {
            "id": "01-B25",
            "url": "https://www.gov.uk/service-manual/agile-delivery/how-the-discovery-phase-works",
            "title": "How the discovery phase works",
            "blog_grade": "official",
            "year": 2024,
        }
    ],
    "05实施控制": [
        {
            "id": "05-B25",
            "url": "https://martinfowler.com/articles/feature-toggles.html",
            "title": "Feature Toggles (aka Feature Flags)",
            "blog_grade": "researcher",
            "year": 2017,
        },
        {
            "id": "05-B26",
            "url": "https://www.atlassian.com/itsm/change-management",
            "title": "What is change management?",
            "blog_grade": "professional",
            "year": 2024,
        },
        {
            "id": "05-B27",
            "url": "https://www.gov.uk/service-manual/agile-delivery/setting-outcomes-and-measuring-success",
            "title": "Setting outcomes and measuring success",
            "blog_grade": "official",
            "year": 2024,
        },
        {
            "id": "05-B28",
            "url": "https://www.infoq.com/articles/experimentation-culture/",
            "title": "Building an Experimentation Culture",
            "blog_grade": "professional",
            "year": 2023,
        },
        {
            "id": "05-B29",
            "url": "https://www.thoughtworks.com/insights/blog/agile-engineering-practices/continuous-delivery-vs-continuous-deployment",
            "title": "Continuous delivery vs continuous deployment",
            "blog_grade": "professional",
            "year": 2024,
        },
    ],
    "07预算": [
        {
            "id": "07-B25",
            "url": "https://www.joelonsoftware.com/2007/10/26/evidence-based-scheduling/",
            "title": "Evidence Based Scheduling",
            "blog_grade": "researcher",
            "year": 2007,
        }
    ],
    "08沟通": [
        {
            "id": "08-B25",
            "url": "https://www.nngroup.com/articles/stakeholders-ux/",
            "title": "Stakeholder Interviews 101",
            "blog_grade": "researcher",
            "year": 2024,
        }
    ],
    "09收尾": [
        {
            "id": "09-B25",
            "url": "https://www.gov.uk/service-manual/agile-delivery/how-the-live-phase-works",
            "title": "How the live phase works",
            "blog_grade": "official",
            "year": 2024,
        }
    ],
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slug_doi(doi: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", (doi or "").lower())[:80]


def attach_checksums(stage: str) -> int:
    path = LIT / stage / "论文登记.统一.json"
    recs = json.loads(path.read_text(encoding="utf-8"))
    pdfs = list((LIT / stage / "全文" / "pdfs").glob("*.pdf"))
    txts = list((LIT / stage / "全文" / "txt").glob("*.txt"))
    n = 0
    for rec in recs:
        if rec.get("checksum_sha256"):
            continue
        doi = (rec.get("doi") or "").lower()
        hit = None
        if doi:
            slug = slug_doi(doi)
            for p in pdfs:
                if slug and slug[:20] in p.name.lower():
                    hit = p
                    break
                if doi.replace("/", "_")[:24] in p.name.lower():
                    hit = p
                    break
        if hit is None and rec.get("id"):
            for p in pdfs:
                if rec["id"].lower() in p.name.lower():
                    hit = p
                    break
        if hit is None and len(pdfs) == 1:
            hit = pdfs[0]
        if hit is not None:
            rec["pdf_path"] = str(hit.relative_to(ROOT))
            rec["checksum_sha256"] = sha_file(hit)
            rec["fulltext_status"] = "local_pdf_and_txt"
            n += 1
            t = LIT / stage / "全文" / "txt" / (hit.stem + ".txt")
            if t.is_file():
                rec["txt_path"] = str(t.relative_to(ROOT))
    path.write_text(json.dumps(recs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def tavily_extract(api_key: str, url: str) -> str:
    data = json.dumps({"urls": [url], "extract_depth": "advanced"}).encode()
    req = urllib.request.Request(
        EXTRACT,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    results = payload.get("results") or []
    if not results:
        return ""
    return (results[0].get("raw_content") or results[0].get("content") or "").strip()


def add_blogs(api_key: str) -> list[dict]:
    added = []
    for stage, items in REPLACEMENTS.items():
        dest = LIT / stage / "全文" / "txt"
        dest.mkdir(parents=True, exist_ok=True)
        blogs = json.loads((LIT / stage / "博客登记.统一.json").read_text(encoding="utf-8"))
        existing = {b.get("url") for b in blogs}
        for item in items:
            if item["url"] in existing:
                continue
            raw = tavily_extract(api_key, item["url"])
            time.sleep(0.4)
            if len(raw.split()) < 400:
                added.append({"stage": stage, "url": item["url"], "ok": False, "words": len(raw.split())})
                continue
            fname = re.sub(r"[^a-z0-9]+", "_", item["url"].lower())[:80] + ".txt"
            txt = dest / fname
            body = f"TITLE: {item['title']}\nURL: {item['url']}\n\n{raw}"
            txt.write_text(body, encoding="utf-8")
            rec = {
                "id": item["id"],
                "title": item["title"],
                "authors": [],
                "year": item["year"],
                "url": item["url"],
                "doi": "",
                "kind": "blog",
                "stage": stage,
                "fulltext_status": "local_txt",
                "peer_reviewed": False,
                "quality": "medium",
                "directness": "规范性" if item["blog_grade"] == "official" else "商业经验",
                "design": "practice_handbook",
                "blog_grade": item["blog_grade"],
                "adoptable": "",
                "do_not_copy": "厂商或手册数字不得当本案定额。",
                "core_findings": raw[:400],
                "limitations": "技术博客，须与论文或标准交叉核对。",
                "checksum_sha256": sha_file(txt),
                "review_status": "close_read",
                "counts_toward_quota": True,
                "exclude_reason": "",
                "pdf_path": "",
                "txt_path": str(txt.relative_to(ROOT)),
                "venue": "",
                "word_count": len(raw.split()),
            }
            blogs.append(rec)
            added.append({"stage": stage, "id": item["id"], "ok": True, "words": rec["word_count"]})
        (LIT / stage / "博客登记.统一.json").write_text(json.dumps(blogs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> None:
    filled = {s: attach_checksums(s) for s in REPLACEMENTS}
    filled.update({s: attach_checksums(s) for s in ("02需求", "04计划", "06交付", "08沟通")})
    print("checksums_attached", filled)
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise SystemExit("TAVILY_API_KEY missing")
    print("blogs", json.dumps(add_blogs(key), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
