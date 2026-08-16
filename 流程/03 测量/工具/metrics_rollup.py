#!/usr/bin/env python3
"""出数：正式行门禁、query 内先聚合、need 等权、cluster bootstrap、正确 DiD。"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import (
    CONFIG,
    MEASURE,
    ROOT,
    case_ledger,
    case_out_dir,
    config_checksum,
    filter_ledger,
    freeze_dir,
    is_formal_row,
    load_table,
    metric_ready,
    read_csv,
    require_case_ids,
    write_csv_atomic,
)

LEDGER = MEASURE / "台账" / "samples.csv"
OUT = MEASURE / "出数" / "metrics_daily.csv"
DID_OUT = MEASURE / "出数" / "did.csv"
COVER_OUT = MEASURE / "出数" / "coverage.csv"
MIN_DID_CLUSTERS = 2

FIELDNAMES = [
    "date",
    "platform",
    "channel",
    "query_set",
    "city",
    "product_mode",
    "n_planned",
    "n_valid",
    "n_limited",
    "n_unscored",
    "p_mention",
    "p_mention_lo",
    "p_mention_hi",
    "p_mention_p",
    "p_mention_p_holm",
    "p_recommend",
    "p_recommend_lo",
    "p_recommend_hi",
    "p_wrong",
    "p_owned",
    "p_fingerprint",
    "p_sov",
    "p_competitor",
    "jaccard_brand_vs_prev",
    "jaccard_source_sameday",
    "jaccard_source_24h",
    "p_mention_roll14",
    "n_bootstrap",
    "n_clusters",
    "notes",
    "case_id",
    "project_id",
    "freeze_id",
    "config_checksum",
]


def domains(source_raw: str) -> set[str]:
    out = set()
    for token in re.split(r"[;\s]+", source_raw or ""):
        token = token.strip()
        if not token or token == "unknown":
            continue
        if "://" in token:
            host = urlparse(token).netloc.lower().removeprefix("www.")
            if host:
                out.add(host)
        elif "." in token and " " not in token:
            out.add(token.lower().removeprefix("www."))
    return out


def seed_for(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


def query_mean(recs: list[dict], field: str) -> float | None:
    vals = []
    for r in recs:
        if field == "mention" and metric_ready(r, "mention"):
            vals.append(1 if r["mention"] == "1" else 0)
        elif field == "recommend" and metric_ready(r, "recommend"):
            vals.append(1 if int(r["recommend"]) >= 1 else 0)
        elif field == "wrong" and metric_ready(r, "wrong"):
            vals.append(1 if r["accuracy"] in {"wrong", "conflict"} else 0)
        elif field == "owned" and metric_ready(r, "owned"):
            vals.append(1 if r["source_owned"] == "1" else 0)
        elif field == "fingerprint" and metric_ready(r, "fingerprint"):
            vals.append(1 if r["fingerprint_hit"] == "1" else 0)
        elif field == "competitor" and metric_ready(r, "competitor"):
            vals.append(1 if r["competitor_hit"] == "1" else 0)
    if not vals:
        return None
    return sum(vals) / len(vals)


def need_cluster_means(qmap: dict[str, dict], by_query: dict[str, list[dict]], field: str) -> dict[str, float]:
    need_vals: dict[str, list[float]] = defaultdict(list)
    for qid, recs in by_query.items():
        q = qmap.get(qid, {})
        if q.get("branded") == "1":
            continue
        m = query_mean(recs, field)
        if m is None:
            continue
        need_vals[q.get("need_id") or qid].append(m)
    return {k: sum(v) / len(v) for k, v in need_vals.items() if v}


def need_equal_mean(qmap: dict[str, dict], by_query: dict[str, list[dict]], field: str) -> float | None:
    means = need_cluster_means(qmap, by_query, field)
    if not means:
        return None
    return sum(means.values()) / len(means)


def cluster_resample_mean(need_means: dict[str, float], drawn: list[str]) -> float | None:
    """Each draw is one observation; a need drawn twice is counted twice."""
    vals = [need_means[k] for k in drawn if k in need_means]
    if not vals:
        return None
    return sum(vals) / len(vals)


def holm_adjust(pvalues: list[float]) -> list[float]:
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvalues[i])
    adj = [0.0] * n
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (n - rank) * pvalues[i])
        running = max(running, val)
        adj[i] = running
    return adj


def apply_p0_mention_holm(rows: list[dict], p0_channels: set[str]) -> None:
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        if r.get("channel") not in p0_channels:
            continue
        if not r.get("p_mention_p"):
            continue
        key = (r.get("date"), r.get("query_set"), r.get("city"), r.get("product_mode"))
        groups[key].append(i)
    for idxs in groups.values():
        raw = [float(rows[i]["p_mention_p"]) for i in idxs]
        adj = holm_adjust(raw)
        for i, a in zip(idxs, adj):
            rows[i]["p_mention_p_holm"] = f"{a:.6f}"


def cluster_bootstrap(
    qmap: dict[str, dict], by_query: dict[str, list[dict]], field: str, seed: int, b: int = 1000
) -> tuple[str, str, str, int, str]:
    need_means = need_cluster_means(qmap, by_query, field)
    keys = list(need_means)
    if len(keys) < 2:
        return "", "", "", len(keys), ""
    rng = random.Random(seed)
    stats = []
    for _ in range(b):
        drawn = [keys[rng.randrange(len(keys))] for _ in range(len(keys))]
        m = cluster_resample_mean(need_means, drawn)
        if m is not None:
            stats.append(m)
    if len(stats) < 20:
        return "", "", "", len(keys), ""
    p_zero = (1 + sum(1 for s in stats if s <= 0)) / (1 + len(stats))
    stats.sort()
    lo = stats[int(0.025 * len(stats))]
    hi = stats[min(len(stats) - 1, int(0.975 * len(stats)))]
    return f"{lo:.4f}", f"{hi:.4f}", str(b), len(keys), f"{p_zero:.6f}"


def fmt(x: float | None) -> str:
    return "" if x is None else f"{x:.4f}"


def jaccard(a: set[str], b: set[str]) -> str:
    if not a and not b:
        return ""
    return f"{len(a & b) / len(a | b):.4f}"


def sov(recs: list[dict]) -> float | None:
    formal = [r for r in recs if metric_ready(r, "mention") and metric_ready(r, "competitor")]
    if len([r for r in formal if r["competitor_hit"] == "1"]) < 2:
        qualified = False
    else:
        qualified = True
    num = 0
    den = 0
    for r in formal:
        self_m = r["mention"] == "1"
        comp = qualified and r["competitor_hit"] == "1"
        if self_m:
            num += 1
            den += 1
        if comp:
            den += 1
    if den == 0:
        return None
    return num / den


def rollup(
    freeze_id: str | None,
    unbranded_only: bool,
    project_id: str | None = None,
    case_id: str | None = None,
) -> list[dict]:
    qrows = load_table("queries.csv", freeze_id, case_id=case_id)
    qmap = {r["query_id"]: r for r in qrows}
    src = case_ledger(case_id) if case_id else LEDGER
    ck = config_checksum(freeze_id, case_id=case_id) if freeze_id else ""
    rows = filter_ledger(read_csv(src), project_id=project_id, freeze_id=freeze_id, checksum=ck)
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    limited: dict[tuple, int] = defaultdict(int)
    unscored: dict[tuple, int] = defaultdict(int)
    planned: dict[tuple, set[str]] = defaultdict(set)

    for r in rows:
        key = (
            r.get("date", ""),
            r.get("platform", ""),
            r.get("channel", ""),
            r.get("query_set", ""),
            r.get("city", ""),
            r.get("product_mode", "") or "unspecified",
        )
        planned[key].add(r.get("query_id", ""))
        if r.get("limited") == "1":
            limited[key] += 1
            continue
        ok, reason = is_formal_row(r, qmap)
        if not ok:
            if reason.startswith("unscored") or reason.startswith("bad_"):
                unscored[key] += 1
            continue
        if unbranded_only and qmap.get(r.get("query_id", ""), {}).get("branded") == "1":
            continue
        buckets[key].append(r)

    dates = sorted({k[0] for k in buckets} | {k[0] for k in planned})
    last_brand: dict[tuple, set[str]] = {}
    last_src: dict[tuple, set[str]] = {}
    mention_hist: dict[tuple, dict[str, float]] = defaultdict(dict)
    out = []
    for d in dates:
        for key in sorted(k for k in set(list(buckets) + list(planned)) if k[0] == d):
            recs = buckets.get(key, [])
            by_query: dict[str, list[dict]] = defaultdict(list)
            for r in recs:
                by_query[r["query_id"]].append(r)
            p_m = need_equal_mean(qmap, by_query, "mention")
            p_r = need_equal_mean(qmap, by_query, "recommend")
            lo_m, hi_m, nb, nc, p_m_raw = cluster_bootstrap(qmap, by_query, "mention", seed_for(*key, "m"))
            lo_r, hi_r, _, _, _ = cluster_bootstrap(qmap, by_query, "recommend", seed_for(*key, "r"))
            mentioned = {qid for qid, rs in by_query.items() if query_mean(rs, "mention") and query_mean(rs, "mention") > 0}
            src_by_run: dict[str, set[str]] = defaultdict(set)
            all_src: set[str] = set()
            for r in recs:
                ds = domains(r.get("source_raw", ""))
                src_by_run[str(r.get("run_index", ""))] |= ds
                all_src |= ds
            runs = list(src_by_run)
            if len(runs) >= 2:
                jac_sd = jaccard(src_by_run[runs[0]], src_by_run[runs[1]])
            else:
                jac_sd = ""
            slice_key = key[1:]
            jac_b = jaccard(mentioned, last_brand.get(slice_key, set())) if last_brand.get(slice_key) else ""
            jac_24 = jaccard(all_src, last_src.get(slice_key, set())) if last_src.get(slice_key) else ""
            mention_hist[slice_key][d] = p_m if p_m is not None else float("nan")
            window = []
            day0 = datetime.strptime(d, "%Y-%m-%d")
            for i in range(14):
                ds = (day0 - timedelta(days=i)).strftime("%Y-%m-%d")
                v = mention_hist[slice_key].get(ds)
                if v is not None and v == v:
                    window.append(v)
            roll = sum(window) / len(window) if window else None
            out.append(
                {
                    "date": d,
                    "platform": key[1],
                    "channel": key[2],
                    "query_set": key[3],
                    "city": key[4],
                    "product_mode": key[5],
                    "n_planned": str(len(planned.get(key, set()))),
                    "n_valid": str(len(recs)),
                    "n_limited": str(limited.get(key, 0)),
                    "n_unscored": str(unscored.get(key, 0)),
                    "p_mention": fmt(p_m),
                    "p_mention_lo": lo_m,
                    "p_mention_hi": hi_m,
                    "p_mention_p": p_m_raw,
                    "p_mention_p_holm": "",
                    "p_recommend": fmt(p_r),
                    "p_recommend_lo": lo_r,
                    "p_recommend_hi": hi_r,
                    "p_wrong": fmt(need_equal_mean(qmap, by_query, "wrong")),
                    "p_owned": fmt(need_equal_mean(qmap, by_query, "owned")),
                    "p_fingerprint": fmt(need_equal_mean(qmap, by_query, "fingerprint")),
                    "p_sov": fmt(sov(recs)),
                    "p_competitor": fmt(need_equal_mean(qmap, by_query, "competitor")),
                    "jaccard_brand_vs_prev": jac_b,
                    "jaccard_source_sameday": jac_sd,
                    "jaccard_source_24h": jac_24,
                    "p_mention_roll14": fmt(roll),
                    "n_bootstrap": nb,
                    "n_clusters": str(nc),
                    "notes": "need_equal_cluster_bootstrap",
                    "case_id": case_id or "",
                    "project_id": project_id or "",
                    "freeze_id": freeze_id or "",
                    "config_checksum": ck,
                }
            )
            last_brand[slice_key] = mentioned
            last_src[slice_key] = all_src
    proj = load_table("project.csv", freeze_id, case_id=case_id)
    mt = (proj[0].get("multiple_testing") if proj else "") or ""
    if "holm" in mt.lower():
        plats = load_table("platforms.csv", freeze_id, case_id=case_id)
        p0 = {r["channel"] for r in plats if r.get("tier") == "P0" and r.get("active") == "1"}
        apply_p0_mention_holm(out, p0)
    dest = case_out_dir(case_id) / "metrics_daily.csv" if case_id else OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_csv_atomic(dest, FIELDNAMES, out)
    return out


def coverage_from(
    plats: list[dict],
    qids: list[str],
    rows: list[dict],
    day: str | None = None,
    qmap: dict[str, dict] | None = None,
) -> list[dict]:
    if day:
        rows = [r for r in rows if r.get("date") == day]
    out = []
    for p in plats:
        ch = p["channel"]
        have = {
            r["query_id"]
            for r in rows
            if r.get("channel") == ch and is_formal_row(r, qmap)[0]
        }
        missing = [q for q in qids if q not in have]
        out.append(
            {
                "channel": ch,
                "tier": p.get("tier", ""),
                "n_expected": str(len(qids)),
                "n_present": str(len(have & set(qids))),
                "missing": ";".join(missing),
                "complete": "1" if not missing else "0",
            }
        )
    return out


def p0_coverage_gap(cov_rows: list[dict]) -> list[str]:
    return [r["channel"] for r in cov_rows if r.get("complete") != "1" and r.get("tier") == "P0"]


def format_p0_coverage_fail(incomplete: list[str]) -> str:
    return "覆盖不全: " + ",".join(incomplete)


def coverage(
    freeze_id: str | None,
    day: str | None,
    project_id: str | None = None,
    case_id: str | None = None,
) -> list[dict]:
    plats = [r for r in load_table("platforms.csv", freeze_id, case_id=case_id) if r.get("active") == "1" and r.get("tier") in {"P0", "P1"}]
    qids = [r["query_id"] for r in load_table("queries.csv", freeze_id, case_id=case_id) if r.get("active") == "1" and r.get("set") in {"core", "holdout"}]
    src = case_ledger(case_id) if case_id else LEDGER
    ck = config_checksum(freeze_id, case_id=case_id) if freeze_id else ""
    rows = filter_ledger(read_csv(src), project_id=project_id, freeze_id=freeze_id, checksum=ck)
    qmap = {r["query_id"]: r for r in load_table("queries.csv", freeze_id, case_id=case_id)}
    dest = case_out_dir(case_id) / "coverage.csv" if case_id else COVER_OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = coverage_from(plats, qids, rows, day, qmap=qmap)
    ident = {
        "case_id": case_id or "",
        "project_id": project_id or "",
        "freeze_id": freeze_id or "",
        "config_checksum": ck,
        "evidence_run_id": next_evidence_run_id(dest.parent),
    }
    for row in out:
        row.update(ident)
    write_csv_atomic(dest, COVER_FIELDS, out)
    publish_evidence(dest.parent, ident)
    return out


DID_FIELDS = [
    "channel",
    "metric",
    "pre",
    "post",
    "did",
    "did_lo",
    "did_hi",
    "excludes_zero",
    "n_treat_clusters",
    "n_hold_clusters",
    "causal_claim",
    "verdict",
    "case_id",
    "project_id",
    "freeze_id",
    "config_checksum",
    "evidence_run_id",
]

COVER_FIELDS = [
    "channel",
    "tier",
    "n_expected",
    "n_present",
    "missing",
    "complete",
    "case_id",
    "project_id",
    "freeze_id",
    "config_checksum",
    "evidence_run_id",
]

EVIDENCE_NAMES = ("did.csv", "coverage.csv")
MANIFEST_HASH_FILES = ("did.csv", "coverage.csv", "metrics_daily.csv")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def parse_invalidation_epoch(text: str) -> int:
    for line in text.splitlines():
        if line.startswith("epoch="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def invalidation_epoch(out_dir: Path) -> int:
    mark = out_dir / "INVALIDATED.txt"
    if not mark.is_file():
        return 0
    return parse_invalidation_epoch(mark.read_text(encoding="utf-8"))


def csv_evidence_run_id(path: Path) -> str:
    rows = read_csv(path)
    ids = {str(r.get("evidence_run_id") or "").strip() for r in rows}
    if len(ids) != 1:
        return ""
    return next(iter(ids))


def next_evidence_run_id(out_dir: Path) -> str:
    return str(invalidation_epoch(out_dir) + 1)


def _live_run_id(out_dir: Path) -> int:
    best = 0
    man = out_dir / "evidence_manifest.json"
    if man.is_file():
        try:
            got = json.loads(man.read_text(encoding="utf-8"))
            best = max(best, int(str(got.get("evidence_run_id") or "0") or 0))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    for name in EVIDENCE_NAMES:
        p = out_dir / name
        if not p.is_file():
            continue
        raw = csv_evidence_run_id(p)
        try:
            best = max(best, int(raw or 0))
        except ValueError:
            pass
    return best


def invalidate_evidence(out_dir: Path) -> None:
    """CHANGE 时把现行 did/coverage/manifest 移入 出数/失效/{epoch}/，并写下代次。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    epoch = max(invalidation_epoch(out_dir), _live_run_id(out_dir))
    dest = out_dir / "失效" / str(epoch)
    for name in (*EVIDENCE_NAMES, "evidence_manifest.json"):
        p = out_dir / name
        if not p.is_file():
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / name
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            target = dest / f"{p.stem}_{stamp}{p.suffix}"
        shutil.move(str(p), str(target))
    (out_dir / "INVALIDATED.txt").write_text(
        f"rewind: outputs not current\nepoch={epoch}\n",
        encoding="utf-8",
    )


def write_evidence_manifest(out_dir: Path, ident: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(ident)
    files = {}
    for name in MANIFEST_HASH_FILES:
        p = out_dir / name
        if p.is_file():
            files[name] = _file_digest(p)
    payload["files"] = files
    (out_dir / "evidence_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def evidence_bundle_ok(out_dir: Path, ident: dict) -> bool:
    """两张表与 manifest 身份/哈希一致，且共用晚于作废代次的 evidence_run_id。"""
    did_p = out_dir / "did.csv"
    cov_p = out_dir / "coverage.csv"
    man_p = out_dir / "evidence_manifest.json"
    if not (did_p.is_file() and cov_p.is_file() and man_p.is_file()):
        return False
    try:
        got = json.loads(man_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for key, want in ident.items():
        if str(got.get(key) or "").strip() != str(want or "").strip():
            return False
    files = got.get("files") or {}
    for name, path in (("did.csv", did_p), ("coverage.csv", cov_p)):
        if files.get(name) != _file_digest(path):
            return False
    daily_p = out_dir / "metrics_daily.csv"
    if daily_p.is_file() and files.get("metrics_daily.csv") != _file_digest(daily_p):
        return False
    did_run = csv_evidence_run_id(did_p)
    cov_run = csv_evidence_run_id(cov_p)
    man_run = str(got.get("evidence_run_id") or "").strip()
    ident_run = str(ident.get("evidence_run_id") or "").strip()
    if not did_run or did_run != cov_run or did_run != man_run:
        return False
    if ident_run and ident_run != did_run:
        return False
    try:
        run_n = int(did_run)
    except ValueError:
        return False
    if (out_dir / "INVALIDATED.txt").is_file() and run_n <= invalidation_epoch(out_dir):
        return False
    return True


def publish_evidence(out_dir: Path, ident: dict) -> bool:
    """唯一发布入口：整包新代次通过后，才清掉 INVALIDATED。"""
    write_evidence_manifest(out_dir, ident)
    if not evidence_bundle_ok(out_dir, ident):
        return False
    mark = out_dir / "INVALIDATED.txt"
    if mark.is_file():
        mark.unlink()
    return True


def did_from_rows(
    rows: list[dict],
    qmap: dict[str, dict],
    treat_needs: set[str],
    hold_needs: set[str],
    claim: str,
    pre: str,
    post: str,
    channel_filter: str | None = None,
    identity: dict | None = None,
) -> list[dict]:
    out = []
    channels = sorted({r.get("channel", "") for r in rows if r.get("channel", "").startswith("app_")})
    if channel_filter:
        channels = [c for c in channels if c == channel_filter]
    treat_needs = {n for n in treat_needs if n}
    hold_needs = {n for n in hold_needs if n}
    for ch in channels:
        for metric in ("mention", "recommend"):
            def need_means(day: str, needs: set[str]) -> dict[str, float]:
                recs = [r for r in rows if r.get("date") == day and r.get("channel") == ch]
                by_q: dict[str, list[dict]] = defaultdict(list)
                for r in recs:
                    ok, _ = is_formal_row(r, qmap)
                    if ok:
                        by_q[r["query_id"]].append(r)
                vals: dict[str, list[float]] = defaultdict(list)
                for qid, rs in by_q.items():
                    q = qmap.get(qid, {})
                    if q.get("need_id") not in needs:
                        continue
                    m = query_mean(rs, metric)
                    if m is not None:
                        vals[q["need_id"]].append(m)
                return {k: sum(v) / len(v) for k, v in vals.items()}

            t0, t1 = need_means(pre, treat_needs), need_means(post, treat_needs)
            c0, c1 = need_means(pre, hold_needs), need_means(post, hold_needs)
            common_t = sorted(set(t0) & set(t1))
            common_c = sorted(set(c0) & set(c1))
            if len(common_t) < MIN_DID_CLUSTERS or len(common_c) < MIN_DID_CLUSTERS:
                label = "insufficient_clusters" if not common_t or not common_c else "degenerate_cluster"
                out.append(
                    {
                        "channel": ch,
                        "metric": metric,
                        "pre": pre,
                        "post": post,
                        "did": "",
                        "did_lo": "",
                        "did_hi": "",
                        "excludes_zero": "",
                        "n_treat_clusters": str(len(common_t)),
                        "n_hold_clusters": str(len(common_c)),
                        "causal_claim": claim,
                        "verdict": label,
                    }
                )
                continue
            d_t = [t1[k] - t0[k] for k in common_t]
            d_c = [c1[k] - c0[k] for k in common_c]
            point = (sum(d_t) / len(d_t)) - (sum(d_c) / len(d_c))
            rng = random.Random(seed_for(ch, metric, pre, post))
            stats = []
            for _ in range(1000):
                bt = [d_t[rng.randrange(len(d_t))] for _ in d_t]
                bc = [d_c[rng.randrange(len(d_c))] for _ in d_c]
                stats.append(sum(bt) / len(bt) - sum(bc) / len(bc))
            stats.sort()
            lo, hi = stats[25], stats[975]
            excludes = "1" if lo > 0 else "0"
            if claim != "did_isolated":
                verdict = "descriptive_only"
            elif lo > 0:
                verdict = "did_excludes_zero"
            elif hi < 0:
                verdict = "did_negative"
            else:
                verdict = "did_includes_zero"
            out.append(
                {
                    "channel": ch,
                    "metric": metric,
                    "pre": pre,
                    "post": post,
                    "did": f"{point:.4f}",
                    "did_lo": f"{lo:.4f}",
                    "did_hi": f"{hi:.4f}",
                    "excludes_zero": excludes,
                    "n_treat_clusters": str(len(common_t)),
                    "n_hold_clusters": str(len(common_c)),
                    "causal_claim": claim,
                    "verdict": verdict,
                }
            )
    ident = identity or {}
    for row in out:
        row.setdefault("case_id", ident.get("case_id", ""))
        row.setdefault("project_id", ident.get("project_id", ""))
        row.setdefault("freeze_id", ident.get("freeze_id", ""))
        row.setdefault("config_checksum", ident.get("config_checksum", ""))
        row.setdefault("evidence_run_id", ident.get("evidence_run_id", ""))
    return out


def did(
    pre: str,
    post: str,
    freeze_id: str | None,
    channel_filter: str | None,
    project_id: str | None = None,
    case_id: str | None = None,
    out_path: Path | None = None,
) -> list[dict]:
    proj = load_table("project.csv", freeze_id, case_id=case_id)
    claim = (proj[0].get("causal_claim") if proj else "") or "descriptive_until_isolation"
    qmap = {r["query_id"]: r for r in load_table("queries.csv", freeze_id, case_id=case_id)}
    treat_needs = set((proj[0].get("treat_need_ids") or "").split(";")) if proj else set()
    hold_needs = set((proj[0].get("holdout_need_ids") or "").split(";")) if proj else set()
    src = case_ledger(case_id) if case_id else LEDGER
    ck = config_checksum(freeze_id, case_id=case_id) if freeze_id else ""
    rows = [
        r
        for r in filter_ledger(read_csv(src), project_id=project_id, freeze_id=freeze_id, checksum=ck)
        if r.get("date") in {pre, post}
    ]
    dest = out_path or (case_out_dir(case_id) / "did.csv" if case_id else DID_OUT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ident = {
        "case_id": case_id or "",
        "project_id": project_id or "",
        "freeze_id": freeze_id or "",
        "config_checksum": ck,
        "evidence_run_id": next_evidence_run_id(dest.parent),
    }
    out = did_from_rows(rows, qmap, treat_needs, hold_needs, claim, pre, post, channel_filter, identity=ident)
    write_csv_atomic(dest, DID_FIELDS, out)
    publish_evidence(dest.parent, ident)
    return out


def top1_agree(
    day: str,
    freeze_id: str | None,
    project_id: str | None = None,
    case_id: str | None = None,
) -> str:
    plats = [r["channel"] for r in load_table("platforms.csv", freeze_id, case_id=case_id) if r.get("tier") == "P0" and r.get("active") == "1"]
    src = case_ledger(case_id) if case_id else LEDGER
    ck = config_checksum(freeze_id, case_id=case_id) if freeze_id else ""
    rows = [
        r
        for r in filter_ledger(read_csv(src), project_id=project_id, freeze_id=freeze_id, checksum=ck)
        if r.get("date") == day and r.get("channel") in plats
    ]
    by_q: dict[str, dict[str, str]] = defaultdict(dict)
    for r in rows:
        ent = (r.get("top1_entity") or "").strip()
        if ent:
            by_q[r["query_id"]][r["channel"]] = ent
    scored = 0
    agree = 0
    for qid, m in by_q.items():
        if len(m) < len(plats):
            continue
        scored += 1
        if len(set(m.values())) == 1:
            agree += 1
    if not scored:
        return ""
    return f"{agree / scored:.4f}"


def main() -> None:
    p = argparse.ArgumentParser(description="GEO 出数（聚类 bootstrap + 正式行门禁）")
    p.add_argument("--date", help="覆盖检查用的日期")
    p.add_argument("--freeze-id")
    p.add_argument("--include-branded", action="store_true")
    p.add_argument("--did-pre")
    p.add_argument("--did-post")
    p.add_argument("--require-coverage", action="store_true")
    p.add_argument("--project-id", dest="project_id", required=True)
    p.add_argument("--case-id", dest="case_id", required=True)
    args = p.parse_args()
    require_case_ids(args.case_id, args.project_id)
    freeze = args.freeze_id
    try:
        fd = freeze_dir(freeze, case_id=args.case_id)
    except SystemExit as e:
        raise
    print(f"freeze={fd.name} checksum={config_checksum(freeze, case_id=args.case_id)}")
    rows = rollup(
        freeze,
        unbranded_only=not args.include_branded,
        project_id=args.project_id,
        case_id=args.case_id,
    )
    cov = coverage(freeze, args.date, project_id=args.project_id, case_id=args.case_id)
    incomplete = p0_coverage_gap(cov)
    if args.require_coverage and incomplete:
        raise SystemExit(format_p0_coverage_fail(incomplete))
    if args.did_pre and args.did_post:
        did_rows = did(args.did_pre, args.did_post, freeze, None, project_id=args.project_id, case_id=args.case_id)
        print(f"did rows={len(did_rows)} -> {DID_OUT.relative_to(ROOT)}")
    if args.date:
        print("top1_p0", top1_agree(args.date, freeze, project_id=args.project_id, case_id=args.case_id) or "n/a")
    print(f"wrote {len(rows)} slices -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
