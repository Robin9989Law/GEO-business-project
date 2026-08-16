#!/usr/bin/env python3
"""Fix peer_reviewed/high conflicts, fill blog_grade, rebuild source tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlparse

LIT = Path(__file__).resolve().parents[1]

OFFICIAL = {
    "pmi.org",
    "apm.org.uk",
    "gov.uk",
    "iso.org",
    "nist.gov",
    "developer.mozilla.org",
    "wcu.edu",
    "projectmanagement.com",
    "pmlearning.org",
    "committees.parliament.uk",
    "scientific-publications.ukaea.uk",
}
RESEARCHER = {
    "martinfowler.com",
    "joelonsoftware.com",
    "blog.codinghorror.com",
    "pressbooks.bccampus.ca",
    "pressbooks.ulib.csuohio.edu",
    "devopsknowledge.hashnode.dev",
}
VENDOR = {
    "projectmanager.com",
    "plane.so",
    "teamgantt.com",
    "asana.com",
    "monday.com",
    "salesforce.com",
    "statsig.com",
    "wrike.com",
    "gong.io",
    "mailchimp.com",
    "highspot.com",
    "sybill.ai",
    "salesmotion.io",
    "prolifiq.com",
    "mindtickle.com",
    "avoma.com",
    "sifthub.io",
    "saber.app",
    "blog.sellible.ai",
    "upliftsales.com.au",
    "tempo.io",
    "nulab.com",
    "smartpm.com",
    "plan.io",
    "workamajig.com",
    "rock.so",
    "optimizely.com",
    "airship.com",
    "dripagency.de",
    "wrike.com",
    "larksuite.com",
    "epicflow.com",
    "lucid.co",
    "testrail.com",
    "testsigma.com",
    "marker.io",
    "bug0.com",
    "bugfree.ai",
    "cassandra.app",
    "prescientai.com",
    "testfiesta.com",
    "enkonix.com",
    "airfocus.com",
    "cleverx.com",
    "precisely.com",
    "otrs.com",
    "paloaltonetworks.com",
    "cloudquery.io",
    "help.sonatype.com",
    "sec.cloudapps.cisco.com",
    "documents.buywithprime.amazon.com",
    "tigernix.com",
    "productive.io",
    "shibumi.com",
    "projstream.com",
    "galorath.com",
    "pontistechnology.com",
    "manifest.ly",
    "projectmanagertemplate.com",
    "flevy.com",
    "itonics-innovation.com",
    "goldeneggcheck.com",
    "volusiabusinessresources.com",
    "htae.net",
    "projectsnco.com",
    "meddicc.com",
    "leanb2bbook.com",
    "simon-kucher.com",
    "mtdsalestraining.com",
}
NON_SCHEMA = {
    "encyclopedia": "professional",
    "vendor_marketing": "vendor",
    "practitioner": "professional",
    "policy": "official",
    "technical_report": "official",
}


def host_of(url: str) -> str:
    h = urlparse(url or "").netloc.lower()
    if h.startswith("www."):
        h = h[4:]
    return h


def grade_for(url: str, current: str = "") -> str:
    cur = (current or "").strip()
    if cur in {"official", "researcher", "professional", "vendor"}:
        return cur
    if cur in NON_SCHEMA:
        return NON_SCHEMA[cur]
    h = host_of(url)
    if h in OFFICIAL or h.endswith(".gov") or h.endswith(".gov.uk") or h.endswith(".edu"):
        return "official"
    if h in RESEARCHER or h.endswith(".ac.uk"):
        return "researcher"
    if h in VENDOR:
        return "vendor"
    return "professional"


def load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, rows: list) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    pr_fixed = 0
    blog_fixed = 0
    for p in sorted(LIT.glob("*/论文登记.统一.json")):
        rows = load(p)
        changed = False
        for r in rows:
            if r.get("kind") == "paper" and r.get("quality") == "high" and r.get("peer_reviewed") is False:
                r["peer_reviewed"] = True
                pr_fixed += 1
                changed = True
        if changed:
            dump(p, rows)
    for p in sorted(LIT.glob("*/博客登记.统一.json")):
        rows = load(p)
        changed = False
        for r in rows:
            if r.get("kind") != "blog":
                continue
            old = str(r.get("blog_grade") or "").strip()
            new = grade_for(r.get("url") or "", old)
            if new != old:
                r["blog_grade"] = new
                blog_fixed += 1
                changed = True
            elif not old and r.get("counts_toward_quota"):
                r["blog_grade"] = new
                blog_fixed += 1
                changed = True
        if changed:
            dump(p, rows)

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
        "blog_grade",
    ]
    all_rows: list[dict] = []
    for kind in ("论文登记.统一.json", "博客登记.统一.json", "标准登记.统一.json"):
        for p in sorted(LIT.glob(f"*/{kind}")):
            all_rows.extend(load(p))
    all_rows.sort(key=lambda r: (str(r.get("stage") or ""), str(r.get("id") or "")))

    def write_csv(path: Path, with_grade: bool) -> None:
        cols = fields if with_grade else [c for c in fields if c != "blog_grade"]
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in all_rows:
                row = {k: r.get(k, "") for k in cols}
                if "year" in row and row["year"] is None:
                    row["year"] = ""
                w.writerow(row)

    write_csv(LIT / "来源去重总表.csv", True)
    write_csv(LIT / "来源去重总表.统一.csv", False)
    print(f"peer_reviewed fixed={pr_fixed} blog_grade fixed={blog_fixed} table_rows={len(all_rows)}")


if __name__ == "__main__":
    main()
