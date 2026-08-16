#!/usr/bin/env python3
"""Tavily 检索博客与开放全文。密钥只读 TAVILY_API_KEY，不写仓库。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIT = ROOT / "研究" / "业务流程文献"
WORK = LIT / "_work"
SEARCH = "https://api.tavily.com/search"
EXTRACT = "https://api.tavily.com/extract"

BLOG_DOMAINS = [
    "pmi.org",
    "apm.org.uk",
    "prince2.com",
    "iso.org",
    "ieee.org",
    "computer.org",
    "sei.cmu.edu",
    "martinfowler.com",
    "thoughtworks.com",
    "atlassian.com",
    "gov.uk",
    "18f.gsa.gov",
    "nasa.gov",
    "nngroup.com",
    "infoq.com",
    "acm.org",
    " construx.com".strip(),
    "scrum.org",
    "mountaingoatsoftware.com",
    "joelonsoftware.com",
    "thepragmaticengineer.com",
    "microsoft.com",
    "google.com",
    "aws.amazon.com",
    "gov.cn",
    "cnblogs.com",
    "infoq.cn",
    "juejin.cn",
]

VENDOR_HINTS = (
    "salesforce",
    "hubspot",
    "oracle",
    "sap ",
    "monday.com",
    "asana",
    "clickup",
    "wrike",
    "smartsheet",
    "jira software pricing",
)

STAGE_BLOG_QUERIES = {
    "01洽谈": [
        "B2B sales discovery interview questions official playbook",
        "MEDDIC BANT opportunity qualification disqualify deal",
        "consultative selling do not overpromise product fit",
        "solution selling product line selection intake",
        "sales ethics no guarantee claims discovery call",
    ],
    "02需求": [
        "requirements elicitation workshop techniques engineering",
        "requirements traceability matrix acceptance criteria",
        "agile requirements change control baseline",
        "goal oriented requirements need classification",
        "IEEE requirements specification best practice blog",
    ],
    "07预算": [
        "software effort estimation planning poker contingency",
        "project budget reserve rework capacity hours",
        "reference class forecasting project cost overrun",
        "COCOMO analogy expert judgment estimation blog",
        "do not include unproven optional work in quote",
    ],
    "08沟通": [
        "project stakeholder analysis communication matrix",
        "RACI decision rights escalation path project",
        "status report meeting decision log facilitation",
        "do not present API metrics as user-facing results",
        "executive reporting evidence hierarchy primary table",
    ],
    "04计划": [
        "work breakdown structure rolling wave planning",
        "critical path schedule baseline dependencies WBS",
        "RACI milestone project schedule blog",
        "product based planning PRINCE2 WBS",
        "retest window is execution not baseline planning",
    ],
    "05实施控制": [
        "earned value project control change request",
        "holdout group experiment do not contaminate control",
        "intervention complete date waiting period retest",
        "issue risk change log closed loop project control",
        "online experiment holdout integrity blog",
    ],
    "06交付": [
        "user acceptance testing delivery checklist checksum",
        "verification validation customer accept reject rework",
        "configuration management release integrity hash",
        "requirements to test traceability acceptance matrix",
        "stage gate review deliverable handover",
    ],
    "09收尾": [
        "project closeout lessons learned archive checklist",
        "post project review knowledge transfer desensitize",
        "benefits realization do not reopen rejected scope",
        "project close phase formal document inventory",
        "lessons learned without customer confidential data",
    ],
}

PAPER_HELP_QUERIES = {
    "01洽谈": "open access PDF sales discovery qualification industrial marketing",
    "02需求": "open access PDF requirements engineering elicitation traceability",
    "07预算": "open access PDF software effort estimation systematic review",
    "08沟通": "open access PDF project stakeholder communication",
    "04计划": "open access PDF work breakdown structure critical path scheduling",
    "05实施控制": "open access PDF earned value project control online experiment holdout",
    "06交付": "open access PDF user acceptance testing verification validation",
    "09收尾": "open access PDF project closeout lessons learned benefits realization",
}

STAGE_CODE = {
    "01洽谈": "01",
    "02需求": "02",
    "07预算": "07",
    "08沟通": "08",
    "04计划": "04",
    "05实施控制": "05",
    "06交付": "06",
    "09收尾": "09",
}


def post_json(url: str, payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="POST",
    )
    last = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code in {429, 500, 502, 503, 504}:
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(f"Tavily HTTP {exc.code}: {body[:400]}") from exc
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Tavily POST failed {url}: {last}")


def search(api_key: str, query: str, max_results: int = 10, include_raw: bool = False, domains: list[str] | None = None) -> dict:
    q = query
    if not any(y in query for y in ("2023", "2024", "2025", "2026")):
        q = f"{query} 2024 OR 2025 OR 2026"
    payload = {
        "query": q,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_raw_content": include_raw,
        "topic": "general",
    }
    if domains:
        payload["include_domains"] = domains
    return post_json(SEARCH, payload, api_key)


def extract(api_key: str, urls: list[str]) -> dict:
    return post_json(EXTRACT, {"urls": urls, "extract_depth": "advanced"}, api_key)


def norm_url(url: str) -> str:
    u = (url or "").strip().split("#", 1)[0]
    u = re.sub(r"^https?://", "", u, flags=re.I)
    u = re.sub(r"/+$", "", u)
    return u.lower()


def norm_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    return re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", "", t)


def grade_blog(url: str, title: str) -> str:
    host = urllib_host(url)
    blob = f"{host} {title}".lower()
    if any(v in blob for v in VENDOR_HINTS):
        return "vendor"
    official = (
        "pmi.org",
        "apm.org.uk",
        "iso.org",
        "ieee.org",
        "sei.cmu.edu",
        "gov.uk",
        "18f.gsa.gov",
        "nasa.gov",
        "acm.org",
        "computer.org",
    )
    researcher = ("martinfowler.com", "nngroup.com", "joelonsoftware.com", "thepragmaticengineer.com", "infoq.com")
    if any(h in host for h in official):
        return "official"
    if any(h in host for h in researcher):
        return "researcher"
    return "professional"


def urllib_host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "", flags=re.I)
    return (m.group(1) if m else "").lower()


def year_from(text: str) -> int | None:
    years = [int(y) for y in re.findall(r"\b(19|20)\d{2}\b", text or "")]
    years = [y for y in years if 1990 <= y <= 2026]
    return years[0] if years else None


def append_csv(path: Path, fieldnames: list[str], row: dict) -> None:
    exists = path.is_file()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerow(row)


def exclude(stage: str, kind: str, query: str, reason: str, ref: str) -> None:
    append_csv(
        WORK / "排除草稿.csv",
        ["stage", "kind", "query", "reason", "url_or_doi", "date"],
        {
            "stage": stage,
            "kind": kind,
            "query": query,
            "reason": reason,
            "url_or_doi": ref,
            "date": time.strftime("%Y-%m-%d"),
        },
    )


def load_seen() -> set[str]:
    seen = set()
    path = LIT / "来源去重总表.csv"
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("norm_url"):
                    seen.add(norm_url(row["norm_url"]))
                if row.get("title_norm"):
                    seen.add(row["title_norm"])
    return seen


def save_txt(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_blogs(stage: str, api_key: str, target: int) -> dict:
    code = STAGE_CODE[stage]
    dest = LIT / stage / "全文" / "txt"
    dest.mkdir(parents=True, exist_ok=True)
    kept_path = WORK / f"{stage}_blogs.json"
    kept = json.loads(kept_path.read_text(encoding="utf-8")) if kept_path.is_file() else []
    seen = load_seen()
    seen |= {norm_url(k.get("url") or "") for k in kept}
    seen |= {k.get("title_norm") or "" for k in kept}
    for q in STAGE_BLOG_QUERIES[stage]:
        if len(kept) >= target:
            break
        data = search(api_key, q, max_results=8, include_raw=True)
        time.sleep(0.4)
        hits = data.get("results") or []
        need_extract = []
        for hit in hits:
            url = hit.get("url") or ""
            title = hit.get("title") or ""
            raw = (hit.get("raw_content") or "").strip()
            if not url or not title:
                continue
            if any(x in url.lower() for x in ("scholar.google", "sciencedirect.com/science/article", "jstor.org", "wiley.com/doi")):
                exclude(stage, "blog", q, "paywall_or_index_page", url)
                continue
            nu, nt = norm_url(url), norm_title(title)
            if nu in seen or nt in seen:
                continue
            if len(raw.split()) < 400:
                need_extract.append((hit, q))
                continue
            rec = keep_blog(stage, code, dest, kept, hit, raw, q)
            seen.add(nu)
            seen.add(nt)
            print(f"[{stage} blog] {len(kept)}/{target}: {title[:80]}", flush=True)
            if len(kept) >= target:
                break
        if need_extract and len(kept) < target:
            urls = [h[0]["url"] for h in need_extract[:5]]
            try:
                extracted = extract(api_key, urls)
            except Exception as exc:  # noqa: BLE001
                print(f"extract fail: {exc}", flush=True)
                extracted = {"results": []}
            time.sleep(0.4)
            by_url = {norm_url(r.get("url") or ""): r for r in (extracted.get("results") or [])}
            for hit, qq in need_extract:
                if len(kept) >= target:
                    break
                url = hit.get("url") or ""
                title = hit.get("title") or ""
                nu, nt = norm_url(url), norm_title(title)
                if nu in seen or nt in seen:
                    continue
                raw = (by_url.get(nu) or {}).get("raw_content") or hit.get("content") or ""
                if len(str(raw).split()) < 400:
                    exclude(stage, "blog", qq, "fulltext_too_short", url)
                    continue
                rec = keep_blog(stage, code, dest, kept, hit, str(raw), qq)
                seen.add(nu)
                seen.add(nt)
                print(f"[{stage} blog] {len(kept)}/{target}: {title[:80]}", flush=True)
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"stage": stage, "blogs": len(kept)}


def keep_blog(stage: str, code: str, dest: Path, kept: list, hit: dict, raw: str, query: str) -> dict:
    idx = len(kept) + 1
    sid = f"{code}-B{idx:02d}"
    url = hit.get("url") or ""
    title = hit.get("title") or ""
    fname = re.sub(r"[^a-z0-9]+", "_", norm_url(url))[:80] or f"blog_{idx:02d}"
    txt = dest / f"{fname}.txt"
    header = f"TITLE: {title}\nURL: {url}\nQUERY: {query}\n\n"
    digest = save_txt(txt, header + raw)
    rec = {
        "id": sid,
        "title": title,
        "authors": [],
        "institution": urllib_host(url),
        "year": year_from(f"{title} {raw[:800]}") or "",
        "url": url,
        "doi": "",
        "fulltext_status": "local_txt",
        "source_type": "blog",
        "blog_grade": grade_blog(url, title),
        "quality": "medium",
        "stage": stage,
        "core_findings": "",
        "limitations": "技术博客，须与论文或标准交叉核对后方可写入合同。",
        "adoptable": "",
        "do_not_copy": "厂商营销句不得直接写入门禁。",
        "checksum_sha256": digest,
        "txt_path": str(txt.relative_to(ROOT)),
        "word_count": len(raw.split()),
        "query": query,
        "title_norm": norm_title(title),
    }
    kept.append(rec)
    append_csv(
        LIT / "来源去重总表.csv",
        ["source_id", "stage", "kind", "doi", "norm_url", "title_norm", "year", "status"],
        {
            "source_id": sid,
            "stage": stage,
            "kind": "blog",
            "doi": "",
            "norm_url": url,
            "title_norm": rec["title_norm"],
            "year": rec["year"],
            "status": "fulltext",
        },
    )
    return rec


def collect_paper_hints(stage: str, api_key: str) -> dict:
    q = PAPER_HELP_QUERIES[stage]
    data = search(api_key, q + " filetype:pdf", max_results=10, include_raw=False)
    path = WORK / f"{stage}_tavily_paper_hints.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"stage": stage, "hints": len(data.get("results") or [])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append", choices=sorted(STAGE_CODE))
    ap.add_argument("--target", type=int, default=24)
    ap.add_argument("--papers-only", action="store_true")
    ap.add_argument("--blogs-only", action="store_true")
    args = ap.parse_args()
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("TAVILY_API_KEY is not set")
    WORK.mkdir(parents=True, exist_ok=True)
    stages = args.stage or list(STAGE_CODE)
    summary = []
    for stage in stages:
        print(f"=== Tavily {stage} ===", flush=True)
        rec = {"stage": stage}
        if not args.papers_only:
            rec.update(collect_blogs(stage, api_key, args.target))
        if not args.blogs_only:
            rec.update(collect_paper_hints(stage, api_key))
        summary.append(rec)
    (WORK / "tavily_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
