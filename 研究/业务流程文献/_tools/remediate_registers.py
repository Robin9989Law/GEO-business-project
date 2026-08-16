#!/usr/bin/env python3
"""重分类不合格博客、补校验和、写出统一登记与名额表。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

LIT = Path(__file__).resolve().parents[1]
ROOT = LIT.parents[1]
BAD_HOSTS = (
    "linkedin.com",
    "wikipedia.org",
    "youtube.com",
    "youtu.be",
    "stackexchange.com",
    "stackoverflow.com",
)
STAGES = ["01洽谈", "02需求", "07预算", "08沟通", "04计划", "05实施控制", "06交付", "09收尾"]


def sha(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def host_of(url: str) -> str:
    u = url or ""
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u
    return urlparse(u).netloc.lower().replace("www.", "")


def is_invalid_blog(url: str) -> str:
    h = host_of(url)
    if any(b in h for b in BAD_HOSTS):
        return "not_tech_blog_host"
    return ""


def load_json(path: Path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def items_of(data):
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in ("items", "papers", "blogs", "records"):
            if isinstance(data.get(k), list):
                return [x for x in data[k] if isinstance(x, dict)]
    return []


def g(rec: dict, *keys, default=""):
    for k in keys:
        if rec.get(k) not in (None, ""):
            return rec[k]
    return default


def as_list(val):
    if isinstance(val, list):
        return val
    if not val:
        return []
    return [val]


def quality_of(rec: dict, kind: str) -> str:
    q = str(g(rec, "quality", "质量")).lower()
    if q in {"high", "medium", "low", "高", "中", "低"}:
        return {"高": "high", "中": "medium", "低": "low"}.get(q, q)
    if rec.get("peer_reviewed") is True:
        return "high"
    if kind == "standard":
        return "high"
    if kind == "blog":
        grade = rec.get("blog_grade") or rec.get("authority") or ""
        if grade in {"official", "researcher"}:
            return "medium"
        return "medium" if grade == "professional" else "low"
    year = int(g(rec, "year", "年份", default=0) or 0)
    venue = str(g(rec, "venue", "机构", default="")).lower()
    if any(x in venue for x in ("arxiv", "preprint", "ssrn")):
        return "medium"
    if year:
        return "medium"
    return "low"


def directness_of(stage: str, rec: dict, kind: str) -> str:
    if kind == "standard":
        return "规范性"
    title = str(g(rec, "title", "题名")).lower()
    blob = title + " " + str(g(rec, "core_findings", "核心发现", "one_line", "protocol_takeaway"))
    if kind == "blog":
        grade = rec.get("blog_grade") or rec.get("authority") or ""
        if grade == "vendor":
            return "商业经验"
        if grade == "official":
            return "规范性"
        return "商业经验"
    geo = ("geo", "generative engine", "ai visibility", "mention probability", "cold query", "无品牌")
    if any(x in blob.lower() for x in geo):
        return "直接"
    # station-typical isomorphic domains
    return "同构迁移"


def unify_rec(stage: str, kind: str, rec: dict, std_urls: set[str]) -> dict:
    url = str(g(rec, "url", "URL", "norm_url"))
    doi = str(g(rec, "doi", "DOI")).replace("https://doi.org/", "").strip()
    pdf = Path(ROOT / str(g(rec, "pdf_path", default=""))) if g(rec, "pdf_path") else None
    txt = Path(ROOT / str(g(rec, "txt_path", default=""))) if g(rec, "txt_path") else None
    checksum = str(g(rec, "checksum_sha256", "checksum"))
    if not checksum:
        if pdf and pdf.is_file():
            checksum = sha(pdf)
        elif txt and txt.is_file():
            checksum = sha(txt)
    invalid = is_invalid_blog(url) if kind == "blog" else ""
    if kind == "blog" and url.rstrip("/").lower() in std_urls:
        invalid = invalid or "same_url_as_standard"
    counts = not invalid and g(rec, "fulltext_status", "全文状态", "status") not in {
        "excluded",
        "excluded_exam_retake_not_project_wait",
        "excluded_dmv_licensing_off_topic",
        "excluded_cert_exam_retake_off_topic",
        "excluded_usmle_retake_off_topic",
    }
    if str(g(rec, "status")).startswith("excluded"):
        counts = False
        invalid = invalid or str(g(rec, "status"))
    quality = quality_of(rec, kind)
    review = "excluded" if invalid else ("background" if quality == "low" else "close_read")
    return {
        "id": rec.get("id") or "",
        "title": g(rec, "title", "题名"),
        "authors": as_list(g(rec, "authors", "作者", default=[])),
        "year": g(rec, "year", "年份"),
        "url": url,
        "doi": doi,
        "kind": kind,
        "stage": stage,
        "fulltext_status": "excluded" if invalid else (g(rec, "fulltext_status", "全文状态") or "local_txt"),
        "peer_reviewed": bool(rec.get("peer_reviewed")) if kind == "paper" else False,
        "quality": quality,
        "directness": directness_of(stage, rec, kind),
        "design": g(rec, "design", "研究设计") or ("standard" if kind == "standard" else ("blog" if kind == "blog" else "empirical_or_review")),
        "blog_grade": rec.get("blog_grade") or rec.get("authority") or "",
        "adoptable": g(rec, "adoptable", "可采用条款", "protocol_takeaway"),
        "do_not_copy": g(rec, "do_not_copy", "不可照搬"),
        "core_findings": g(rec, "core_findings", "核心发现", "one_line"),
        "limitations": g(rec, "limitations", "限制"),
        "checksum_sha256": checksum,
        "review_status": review,
        "counts_toward_quota": bool(counts) and not invalid,
        "exclude_reason": invalid,
        "pdf_path": g(rec, "pdf_path"),
        "txt_path": g(rec, "txt_path"),
        "venue": g(rec, "venue", "机构", "site", "org", "issuer"),
        "word_count": g(rec, "word_count"),
    }


def fallback_from_dedup(stage: str, kind: str) -> list[dict]:
    rows = []
    with (LIT / "来源去重总表.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("stage") == stage and r.get("kind") == kind:
                rows.append(
                    {
                        "id": r.get("source_id"),
                        "title": r.get("title_norm"),
                        "url": r.get("norm_url"),
                        "doi": r.get("doi"),
                        "year": r.get("year"),
                        "status": r.get("status"),
                    }
                )
    return rows


def main() -> None:
    out_rows = []
    quota = []
    excluded_blogs = []
    for stage in STAGES:
        d = LIT / stage
        std_raw = items_of(load_json(d / "标准登记.json")) or fallback_from_dedup(stage, "standard")
        std_urls = {(r.get("url") or r.get("URL") or r.get("norm_url") or "").rstrip("/").lower() for r in std_raw}
        papers = items_of(load_json(d / "论文登记.json")) or fallback_from_dedup(stage, "paper")
        blogs = items_of(load_json(d / "博客登记.json")) or fallback_from_dedup(stage, "blog")
        standards = std_raw
        u_papers = [unify_rec(stage, "paper", r, std_urls) for r in papers]
        u_blogs = [unify_rec(stage, "blog", r, std_urls) for r in blogs]
        u_std = [unify_rec(stage, "standard", r, set()) for r in standards]
        (d / "论文登记.统一.json").write_text(json.dumps(u_papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (d / "博客登记.统一.json").write_text(json.dumps(u_blogs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (d / "标准登记.统一.json").write_text(json.dumps(u_std, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pq = sum(1 for x in u_papers if x["counts_toward_quota"])
        bq = sum(1 for x in u_blogs if x["counts_toward_quota"])
        sq = len(u_std)
        low_p = sum(1 for x in u_papers if x["quality"] == "low")
        no_ck = sum(1 for x in u_papers if x["counts_toward_quota"] and not x["checksum_sha256"])
        quota.append({"stage": stage, "papers_quota": pq, "blogs_quota": bq, "standards": sq, "low_papers": low_p, "papers_missing_checksum": no_ck, "blogs_needed": max(0, 20 - bq)})
        for x in u_blogs:
            if x["exclude_reason"]:
                excluded_blogs.append(x)
            out_rows.append(x)
        out_rows.extend(u_papers)
        out_rows.extend(u_std)

    fields = [
        "id",
        "stage",
        "kind",
        "title",
        "year",
        "doi",
        "url",
        "quality",
        "directness",
        "peer_reviewed",
        "counts_toward_quota",
        "review_status",
        "checksum_sha256",
        "exclude_reason",
    ]
    with (LIT / "来源去重总表.统一.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    (LIT / "_work" / "quota_after_reclass.json").write_text(json.dumps(quota, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (LIT / "_work" / "blogs_removed.json").write_text(json.dumps(excluded_blogs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(quota, ensure_ascii=False, indent=2))
    print("removed_blogs", len(excluded_blogs))


if __name__ == "__main__":
    main()
