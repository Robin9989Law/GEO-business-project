#!/usr/bin/env python3
"""测量共用字段、冻结路径、正式行校验。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

MEASURE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
CONFIG = MEASURE / "配置"
LEDGER = MEASURE / "台账" / "samples.csv"
CASE_RUNTIME = MEASURE / "案件"

SAMPLE_FIELDS = [
    "sample_id",
    "date",
    "query_id",
    "query_set",
    "treat",
    "platform",
    "channel",
    "run_index",
    "app_version",
    "city",
    "logged_in",
    "fresh_session",
    "answer_text_path",
    "screenshot_path",
    "raw_json_path",
    "mention",
    "recommend",
    "accuracy",
    "source_raw",
    "source_owned",
    "competitor_hit",
    "card_mention",
    "limited",
    "rater",
    "notes",
    "search_triggered",
    "position",
    "sov_eligible",
    "fingerprint_hit",
    "product_mode",
    "project_id",
    "task",
    "freeze_id",
    "config_checksum",
    "run_uuid",
    "retry_of",
    "captured_at",
    "account_cluster",
    "operator",
    "device",
    "top1_entity",
]

SCORE_FIELDS = ("mention", "recommend", "accuracy", "source_owned", "competitor_hit")
ACCURACY_OK = {"absent", "correct", "wrong", "conflict"}


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for raw in reader:
            rows.append({(k or "").lstrip("\ufeff"): v for k, v in raw.items()})
        return rows


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    tmp.replace(path)


def freeze_dir(freeze_id: str | None = None, case_id: str | None = None, extra_roots: list[Path] | None = None) -> Path:
    cands: list[Path] = []
    if freeze_id:
        if extra_roots:
            cands.extend(Path(r) / freeze_id for r in extra_roots)
        if case_id:
            cands.append(CASE_RUNTIME / case_id / "冻结" / freeze_id)
        elif not extra_roots:
            cands.append(CONFIG / "冻结" / freeze_id)
        for d in cands:
            if d.is_dir():
                return d
        raise SystemExit(f"冻结目录不存在: {freeze_id}")
    if case_id:
        case_root = CASE_RUNTIME / case_id / "冻结"
        if case_root.is_dir():
            dated = sorted([p for p in case_root.iterdir() if p.is_dir()], reverse=True)
            if dated:
                return dated[0]
        raise SystemExit(f"本案没有冻结目录: {case_id}")
    root = CONFIG / "冻结"
    dated = sorted([p for p in root.iterdir() if p.is_dir() and p.name[0].isdigit()], reverse=True)
    if dated:
        return dated[0]
    raise SystemExit("没有冻结目录；共享配置不能当冻结")


def load_table(name: str, freeze_id: str | None = None, case_id: str | None = None) -> list[dict]:
    return read_csv(freeze_dir(freeze_id, case_id=case_id) / name)


def config_checksum(freeze_id: str | None = None, case_id: str | None = None) -> str:
    d = freeze_dir(freeze_id, case_id=case_id)
    h = hashlib.sha256()
    required = ("queries.csv", "aliases.csv", "facts.csv", "owned_sources.csv", "platforms.csv", "project.csv")
    for name in required:
        p = d / name
        if not p.exists():
            raise SystemExit(f"冻结缺文件，不能回退活动配置: {p}")
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def case_ledger(case_id: str | None = None) -> Path:
    if case_id:
        return CASE_RUNTIME / case_id / "台账" / "samples.csv"
    return LEDGER


def case_out_dir(case_id: str | None = None) -> Path:
    if case_id:
        return CASE_RUNTIME / case_id / "出数"
    return MEASURE / "出数"


def case_sample_root(case_id: str) -> Path:
    if not case_id:
        raise SystemExit("采集必须提供 case_id")
    return CASE_RUNTIME / case_id / "样本"


def require_case_ids(case_id: str | None, project_id: str | None = None) -> None:
    if not case_id:
        raise SystemExit("需要 --case-id")
    if project_id is not None and not project_id:
        raise SystemExit("需要 --project-id")


def _norm_ids(val: object) -> set[str]:
    return {p.strip() for p in str(val or "").replace(",", ";").split(";") if p.strip()}


def freeze_manifest(freeze_path: Path) -> dict:
    rows = read_csv(freeze_path / "project.csv")
    return rows[0] if rows else {}


def freeze_matches_contract(freeze_path: Path, fields: dict) -> list[str]:
    miss: list[str] = []
    if not freeze_path.is_dir():
        return ["freeze_dir"]
    proj = freeze_manifest(freeze_path)
    if not proj:
        return ["project.csv"]
    pairs = (
        ("project_id", "project_id"),
        ("sop_stage", "sop_stage"),
        ("city", "city"),
        ("vertical", "vertical"),
        ("platforms_required", "platforms_required"),
    )
    for src, dst in pairs:
        left = str(proj.get(src) or "").strip()
        right = str(fields.get(dst) or "").strip()
        if left and right and left != right:
            miss.append(src)
    if _norm_ids(proj.get("treat_need_ids")) != _norm_ids(fields.get("treat_need_ids")):
        miss.append("treat_need_ids")
    if _norm_ids(proj.get("holdout_need_ids")) != _norm_ids(fields.get("holdout_need_ids")):
        miss.append("holdout_need_ids")
    return miss


def filter_ledger(
    rows: list[dict],
    project_id: str | None = None,
    freeze_id: str | None = None,
    checksum: str | None = None,
) -> list[dict]:
    out = []
    for r in rows:
        if project_id and r.get("project_id") != project_id:
            continue
        if freeze_id and r.get("freeze_id") != freeze_id:
            continue
        if checksum and r.get("config_checksum") != checksum:
            continue
        out.append(r)
    return out


def file_exists(rel: str) -> bool:
    if not rel:
        return False
    return (ROOT / rel).exists() or (ROOT / "流程" / rel).exists() or Path(rel).exists()


def is_formal_row(row: dict, queries: dict[str, dict] | None = None) -> tuple[bool, str]:
    if row.get("limited") == "1":
        return False, "limited"
    if row.get("fresh_session") != "1":
        return False, "not_fresh"
    qid = row.get("query_id", "")
    if queries is not None:
        q = queries.get(qid)
        if not q or q.get("active") != "1":
            return False, "inactive_query"
    channel = row.get("channel", "")
    if channel.startswith("app_"):
        if not file_exists(row.get("answer_text_path", "")):
            return False, "missing_txt"
        if not file_exists(row.get("screenshot_path", "").split(";")[0] if row.get("screenshot_path") else ""):
            return False, "missing_screenshot"
    elif channel.startswith("api_"):
        if not file_exists(row.get("raw_json_path", "")):
            return False, "missing_json"
    else:
        return False, "bad_channel"
    for f in SCORE_FIELDS:
        if row.get(f, "") == "":
            return False, f"unscored_{f}"
    if row.get("accuracy") not in ACCURACY_OK:
        return False, "bad_accuracy"
    if row.get("mention") not in {"0", "1"}:
        return False, "bad_mention"
    if row.get("recommend") not in {"0", "1", "2"}:
        return False, "bad_recommend"
    return True, "ok"


def metric_ready(row: dict, field: str) -> bool:
    ok, _ = is_formal_row(row)
    if not ok:
        return False
    if field == "mention":
        return row.get("mention") in {"0", "1"}
    if field == "recommend":
        return row.get("recommend") in {"0", "1", "2"}
    if field == "wrong":
        return row.get("accuracy") in ACCURACY_OK
    if field == "owned":
        return row.get("source_owned") in {"0", "1"}
    if field == "fingerprint":
        return row.get("fingerprint_hit") in {"0", "1"}
    if field == "competitor":
        return row.get("competitor_hit") in {"0", "1"}
    return False


def upsert_ledger(row: dict, ledger_path: Path | None = None) -> str:
    """按 run_uuid 或 sample_id 幂等写入。返回 inserted|updated|skipped_conflict。"""
    dest = ledger_path or LEDGER
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = read_csv(dest)
    if not rows and (not dest.exists() or dest.stat().st_size == 0):
        write_csv_atomic(dest, SAMPLE_FIELDS, [{k: row.get(k, "") for k in SAMPLE_FIELDS}])
        return "inserted"
    key_uuid = row.get("run_uuid", "")
    key_sid = row.get("sample_id", "")
    out = []
    status = "inserted"
    found = False
    for r in rows:
        same = (key_uuid and r.get("run_uuid") == key_uuid) or (
            not key_uuid and r.get("sample_id") == key_sid
        )
        if same:
            found = True
            if r.get("raw_json_path") and r.get("raw_json_path") != row.get("raw_json_path"):
                status = "skipped_conflict"
                out.append(r)
            else:
                merged = {k: r.get(k, "") for k in SAMPLE_FIELDS}
                merged.update({k: row.get(k, merged.get(k, "")) for k in SAMPLE_FIELDS if row.get(k, "") != ""})
                out.append(merged)
                status = "updated"
        else:
            out.append(r)
    if not found:
        out.append({k: row.get(k, "") for k in SAMPLE_FIELDS})
        status = "inserted"
    write_csv_atomic(dest, SAMPLE_FIELDS, out)
    return status
