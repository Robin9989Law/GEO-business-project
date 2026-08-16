#!/usr/bin/env python3
"""第二学术库（Crossref）计数 + Semantic Scholar 前向/后向引文（每站 3 篇锚点）。"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

LIT = Path(__file__).resolve().parents[1]
UA = "GEO-process-lit/1.1 (mailto:geo-research@localhost)"

STAGE_CROSSREF = {
    "01洽谈": "sales discovery OR opportunity qualification OR consultative selling",
    "02需求": "requirements elicitation OR requirements traceability",
    "07预算": "software effort estimation OR planning fallacy",
    "08沟通": "project stakeholder communication OR RACI",
    "04计划": "work breakdown structure OR critical path scheduling",
    "05实施控制": "earned value management OR online controlled experiment holdout",
    "06交付": "user acceptance testing OR software verification validation",
    "09收尾": "project closeout OR lessons learned benefits realization",
}

ANCHORS = {
    "01洽谈": ["10.1007/s11747-025-01096-3", "10.1016/j.indmarman.2023.08.007", "10.1007/s12144-024-06720-z"],
    "02需求": ["10.1145/3767739", "10.1007/s00766-016-0256-4"],
    "07预算": ["10.1109/access.2024.3404879", "10.48550/arxiv.2408.07710", "10.48550/arxiv.2405.01569"],
    "08沟通": [],
    "04计划": ["10.1007/s10479-024-05841-9"],
    "05实施控制": ["10.12821/ijispm120404", "10.48550/arxiv.2312.15574"],
    "06交付": ["10.1145/3767739", "10.1038/s41746-025-01447-y"],
    "09收尾": [],
}


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def crossref_count(query: str) -> dict:
    q = urllib.parse.urlencode(
        {
            "query": query,
            "filter": "from-pub-date:2023-08-01,until-pub-date:2026-08-16,type:journal-article",
            "rows": "0",
            "mailto": "geo-research@localhost",
        }
    )
    data = get_json(f"https://api.crossref.org/works?{q}")
    return {"query": query, "total": (data.get("message") or {}).get("total-results")}


def s2_paper(doi: str) -> dict:
    doi_q = urllib.parse.quote(doi)
    url = (
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi_q}"
        "?fields=title,year,citationCount,referenceCount,influentialCitationCount"
    )
    try:
        data = get_json(url)
    except Exception as exc:  # noqa: BLE001
        return {"doi": doi, "error": str(exc)}
    return {
        "doi": doi,
        "title": data.get("title"),
        "year": data.get("year"),
        "citationCount": data.get("citationCount"),
        "referenceCount": data.get("referenceCount"),
        "influentialCitationCount": data.get("influentialCitationCount"),
        "s2_id": data.get("paperId"),
    }


def openalex_seed_dois(stage: str, n: int = 3) -> list[str]:
    path = LIT / stage / "论文登记.统一.json"
    if not path.is_file():
        return []
    recs = json.loads(path.read_text(encoding="utf-8"))
    dois = []
    for r in recs:
        if r.get("doi") and r.get("counts_toward_quota") and r.get("quality") in {"high", "medium"}:
            dois.append(r["doi"])
        if len(dois) >= n:
            break
    return dois


def main() -> None:
    report = {"crossref": {}, "citations": {}}
    for stage, q in STAGE_CROSSREF.items():
        report["crossref"][stage] = crossref_count(q)
        time.sleep(0.2)
        dois = ANCHORS.get(stage) or openalex_seed_dois(stage)
        cites = []
        for doi in dois[:3]:
            cites.append(s2_paper(doi))
            time.sleep(0.8)
        report["citations"][stage] = cites
        print(stage, report["crossref"][stage]["total"], [c.get("citationCount") for c in cites], flush=True)
    (LIT / "第二库与引文追踪.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
