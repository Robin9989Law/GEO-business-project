#!/usr/bin/env python3
"""Continue 08沟通 OA PDF downloads from candidates_strict.json. No global dedup write."""
from __future__ import annotations

import importlib.util
import json
import os
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

strict = importlib.util.spec_from_file_location("collect_08_strict", WORK / "collect_08_strict.py")
smod = importlib.util.module_from_spec(strict)
assert strict.loader
strict.loader.exec_module(smod)


def main() -> None:
    dest_pdf = LIT / STAGE / "全文" / "pdfs"
    dest_txt = LIT / STAGE / "全文" / "txt"
    dest_pdf.mkdir(parents=True, exist_ok=True)
    dest_txt.mkdir(parents=True, exist_ok=True)
    kept_path = WORK / "08沟通_kept.json"
    cand_path = WORK / "08沟通_candidates_strict.json"
    kept = json.loads(kept_path.read_text(encoding="utf-8")) if kept_path.is_file() else []
    # drop weak leftover from first pass
    drop_doi = {
        "10.4186/ej.2024.28.8.79",  # BIM adoption review
        "10.31893/multirev.2024066",  # leadership technology
    }
    kept2 = []
    for rec in kept:
        doi = mod.norm_doi(rec.get("doi") or "")
        if doi in drop_doi or not smod.on_topic(rec) or not smod.in_window(rec):
            smod.exclude("off_topic_or_weak_first_pass", doi or rec.get("title") or "", rec.get("query") or "")
            continue
        kept2.append(rec)
    kept = kept2

    have = {mod.norm_doi(k.get("doi") or "") for k in kept if k.get("doi")}
    have |= {k.get("title_norm") for k in kept if k.get("title_norm")}
    candidates = json.loads(cand_path.read_text(encoding="utf-8"))

    def rank_key(r: dict) -> tuple:
        return (-len(r.get("topic_cats") or []), -(int(r.get("cited_by_count") or 0)), -(int(r.get("year") or 0)))

    ranked = sorted(candidates, key=rank_key)
    target = 36
    max_try = 140
    tried = 0
    print(f"start kept={len(kept)} cand={len(ranked)}", flush=True)
    for rec in ranked:
        if len(kept) >= target:
            break
        if tried >= max_try:
            break
        if not smod.in_window(rec) or not smod.on_topic(rec):
            continue
        key_d = mod.norm_doi(rec.get("doi") or "")
        key_t = rec.get("title_norm") or ""
        if (key_d and key_d in have) or (key_t and key_t in have):
            continue
        url = rec.get("pdf_url") or ""
        if not url:
            smod.exclude("no_oa_pdf_url", key_d or rec.get("title") or "", rec.get("query") or "")
            continue
        tried += 1
        fname = mod.slug(rec, tried + 100)
        pdf = dest_pdf / f"{fname}.pdf"
        txt = dest_txt / f"{fname}.txt"
        if not pdf.is_file() or pdf.stat().st_size < 4000:
            ok = mod.download(url, pdf)
            if not ok:
                smod.exclude("pdf_download_failed_or_paywall", url, rec.get("query") or "")
                continue
        if not mod.extract_txt(pdf, txt):
            smod.exclude("fulltext_too_short_or_extract_fail", url, rec.get("query") or "")
            if pdf.exists() and pdf.stat().st_size < 8000:
                pdf.unlink(missing_ok=True)
            continue
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
        have.add(key_d)
        have.add(key_t)
        rec["id"] = f"08-P{len(kept):02d}"
        kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"kept {len(kept)}/{target}: {rec.get('year')} {rec.get('title')[:88]} cats={rec.get('topic_cats')}",
            flush=True,
        )

    for i, rec in enumerate(kept, 1):
        rec["id"] = f"08-P{i:02d}"
    kept_path.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"kept": len(kept), "tried": tried}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
