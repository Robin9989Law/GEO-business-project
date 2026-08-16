#!/usr/bin/env python3
"""10 项目文件：原始入库、正式版本、成员中转。不另做软件，全是文件夹。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).resolve().parent / "cases"
PROD_VAULTS = ROOT / "流程" / "10 项目文件" / "案件"

BANNED_CLAIMS = (
    "保证推荐",
    "保证会被推荐",
    "报名因此增长",
    "国内可见性",
    "GEO 已证明",
    "已经优化成功",
    "优化后会涨",
)
STAGES = ("01", "02", "07", "08", "03", "04", "05", "06", "09")
SAFE_NAME = re.compile(r"^[A-Za-z0-9._\u4e00-\u9fff\-]+$")

RAW_FIELDS = ("raw_id", "at", "stage", "title", "filename", "checksum", "kind", "src", "actor", "quarantine")
DOC_FIELDS = (
    "doc_id",
    "title",
    "rev",
    "checksum",
    "gate",
    "stage",
    "status",
    "locked_by",
    "raw_id",
    "path",
    "at",
)
LOCK_FIELDS = ("doc_id", "member", "at", "note")
XFER_FIELDS = ("item_id", "at", "action", "sender", "receiver", "filename", "checksum", "status", "note")
MEMBER_FIELDS = ("member_id", "role", "notes")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fail(msg: str) -> None:
    raise ValueError(msg)


def vault_path(case_id: str, cases_root: Path | None = None, files_root: Path | None = None) -> Path:
    if files_root is not None:
        return Path(files_root) / case_id
    if cases_root is not None:
        return Path(cases_root) / case_id / "vault"
    return PROD_VAULTS / case_id


def public_paths(case_id: str, stage: str = "01") -> dict[str, str]:
    base = f"流程/10 项目文件/案件/{case_id}"
    return {
        "raw": f"{base}/原始/{stage}/",
        "formal": f"{base}/正式/现行/",
        "board": f"{base}/中转/看板.md",
        "inbox_xfer": f"{base}/中转/收件/",
        "vault": f"{base}/",
    }


def _csv_path(vault: Path, rel: str) -> Path:
    return vault / rel


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            rows.append({k: (row.get(k) or "") for k in fields})
        return rows


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def _append_csv(path: Path, fields: tuple[str, ...], row: dict) -> None:
    rows = _read_csv(path, fields)
    rows.append(row)
    _write_csv(path, fields, rows)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_banned(path: Path) -> list[str]:
    if path.suffix.lower() not in {".md", ".txt", ".csv", ".json"}:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return [bad for bad in BANNED_CLAIMS if bad in text]


def _scan_banned(path: Path) -> None:
    hits = find_banned(path)
    if hits:
        _fail(f"banned claim in {path.name}: {hits[0]}")


def _safe(name: str) -> str:
    name = Path(name).name
    if not name or name in {".", ".."}:
        _fail("bad filename")
    return name


def _is_measure(path: Path) -> bool:
    parts = {p.name for p in path.resolve().parents}
    return "03 测量" in parts


def init_vault(case_id: str, cases_root: Path | None = None, files_root: Path | None = None) -> Path:
    vault = vault_path(case_id, cases_root, files_root)
    if (vault / "原始" / "登记.csv").is_file():
        return vault
    for stage in STAGES:
        (vault / "原始" / stage).mkdir(parents=True, exist_ok=True)
    (vault / "正式" / "现行").mkdir(parents=True, exist_ok=True)
    (vault / "正式" / "版本").mkdir(parents=True, exist_ok=True)
    (vault / "正式" / "失效").mkdir(parents=True, exist_ok=True)
    (vault / "中转" / "收件").mkdir(parents=True, exist_ok=True)
    (vault / "中转" / "待取").mkdir(parents=True, exist_ok=True)
    (vault / "中转" / "已取").mkdir(parents=True, exist_ok=True)
    _write_csv(vault / "原始" / "登记.csv", RAW_FIELDS, [])
    _write_csv(vault / "正式" / "清单.csv", DOC_FIELDS, [])
    _write_csv(vault / "正式" / "锁.csv", LOCK_FIELDS, [])
    _write_csv(vault / "中转" / "往来.csv", XFER_FIELDS, [])
    _write_csv(vault / "成员登记.csv", MEMBER_FIELDS, [])
    (vault / "中转" / "看板.md").write_text(
        f"# 中转看板（{case_id}）\n\n暂无待取。Agent 每次开口先读本页。\n",
        encoding="utf-8",
    )
    (vault / "README.md").write_text(
        f"# 本案文件库（{case_id}）\n\n"
        "- 人交的资料进 `原始/`，不要改 `正式/现行/`。\n"
        "- 过门后由 Agent 发布到 `正式/`，旧版留在 `正式/版本/`。\n"
        "- 成员互传走 `中转/`，先看 `中转/看板.md`。\n"
        "- `流程/03 测量/` 实物不复制进来，只登记指针。\n",
        encoding="utf-8",
    )
    write_board(case_id, cases_root, files_root)
    return vault


def deposit_raw(
    case_id: str,
    src: str | Path,
    stage: str,
    title: str = "",
    actor: str = "agent",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    if stage not in STAGES:
        _fail(f"bad stage {stage}")
    src_p = Path(src)
    if not src_p.is_file():
        _fail(f"no file {src_p}")
    hits = find_banned(src_p)
    vault = init_vault(case_id, cases_root, files_root)
    dest_dir = vault / "原始" / stage
    if hits:
        dest_dir = dest_dir / "隔离"
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = _safe(src_p.name)
    pointer = _is_measure(src_p)
    raw_id = f"R{len(_read_csv(vault / '原始' / '登记.csv', RAW_FIELDS)) + 1:04d}"
    if pointer:
        dest = dest_dir / f"{src_p.stem}.ptr.md"
        try:
            rel = src_p.resolve().relative_to(ROOT)
        except ValueError:
            rel = src_p
        dest.write_text(
            f"# 指针（不复制测量实物）\n\n- 源：`{rel}`\n- 标题：{title or src_p.name}\n- 登记：{raw_id}\n",
            encoding="utf-8",
        )
        kind = "pointer"
        checksum = _sha256(src_p)
    else:
        dest = dest_dir / fname
        if dest.exists() and _sha256(dest) != _sha256(src_p):
            dest = dest_dir / f"{src_p.stem}_{raw_id}{src_p.suffix}"
        shutil.copy2(src_p, dest)
        kind = "copy"
        checksum = _sha256(dest)
    row = {
        "raw_id": raw_id,
        "at": now(),
        "stage": stage,
        "title": title or fname,
        "filename": dest.name,
        "checksum": checksum,
        "kind": "quarantine" if hits else kind,
        "src": str(src_p),
        "actor": actor,
        "quarantine": "是" if hits else "",
    }
    _append_csv(vault / "原始" / "登记.csv", RAW_FIELDS, row)
    return row


def deposit_inbox(case_id: str, stage: str, cases_root: Path | None = None, files_root: Path | None = None) -> list[dict]:
    inbox = (cases_root or DEFAULT_CASES) / case_id / "inbox"
    if not inbox.is_dir():
        return []
    vault = init_vault(case_id, cases_root, files_root)
    seen = {(r.get("stage"), r.get("checksum")) for r in _read_csv(vault / "原始" / "登记.csv", RAW_FIELDS)}
    candidates: list[Path] = []
    staged = inbox / stage
    if staged.is_dir():
        candidates.extend(p for p in staged.iterdir() if p.is_file() and not p.name.startswith("."))
    for p in inbox.iterdir():
        if p.is_file() and not p.name.startswith(".") and (p.name.startswith(stage + "_") or p.name.startswith(stage)):
            candidates.append(p)
    out: list[dict] = []
    for p in sorted(candidates, key=lambda x: x.name):
        digest = _sha256(p)
        if (stage, digest) in seen:
            continue
        row = deposit_raw(case_id, p, stage, title=p.stem, cases_root=cases_root, files_root=files_root)
        seen.add((stage, digest))
        out.append(row)
    return out


def _docs(vault: Path) -> list[dict]:
    return _read_csv(vault / "正式" / "清单.csv", DOC_FIELDS)


def _locks(vault: Path) -> dict[str, dict]:
    return {r["doc_id"]: r for r in _read_csv(vault / "正式" / "锁.csv", LOCK_FIELDS) if r.get("doc_id")}


def _next_rev(docs: list[dict], doc_id: str) -> int:
    revs = [int(r["rev"]) for r in docs if r.get("doc_id") == doc_id and str(r.get("rev", "")).isdigit()]
    return (max(revs) + 1) if revs else 1


def _require_doc_id(doc_id: str) -> str:
    doc_id = doc_id.strip()
    if not doc_id or not SAFE_NAME.match(doc_id):
        _fail(f"bad doc_id {doc_id}")
    return doc_id


def promote_formal(
    case_id: str,
    src: str | Path,
    doc_id: str,
    gate: str = "",
    stage: str = "",
    title: str = "",
    raw_id: str = "",
    actor: str = "agent",
    member: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    src_p = Path(src)
    if not src_p.is_file():
        _fail(f"no file {src_p}")
    _scan_banned(src_p)
    doc_id = _require_doc_id(doc_id)
    vault = init_vault(case_id, cases_root, files_root)
    locks = _locks(vault)
    if doc_id in locks and member and locks[doc_id]["member"] != member:
        _fail(f"{doc_id} locked by {locks[doc_id]['member']}")
    if doc_id in locks and not member:
        _fail(f"{doc_id} locked by {locks[doc_id]['member']}; checkin with --member")
    docs = _docs(vault)
    rev = _next_rev(docs, doc_id)
    suffix = src_p.suffix or ".md"
    ver_dir = vault / "正式" / "版本" / f"v{rev:03d}"
    ver_dir.mkdir(parents=True, exist_ok=True)
    stored = ver_dir / f"{doc_id}{suffix}"
    shutil.copy2(src_p, stored)
    current = vault / "正式" / "现行" / f"{doc_id}{suffix}"
    shutil.copy2(src_p, current)
    checksum = _sha256(stored)
    try:
        rel = stored.resolve().relative_to(ROOT)
        rel_s = str(rel)
    except ValueError:
        rel_s = str(stored)
    row = {
        "doc_id": doc_id,
        "title": title or doc_id,
        "rev": str(rev),
        "checksum": checksum,
        "gate": gate,
        "stage": stage,
        "status": "现行",
        "locked_by": "",
        "raw_id": raw_id,
        "path": rel_s,
        "at": now(),
    }
    for old in docs:
        if old.get("doc_id") == doc_id:
            old["status"] = "历史"
    docs.append(row)
    _write_csv(vault / "正式" / "清单.csv", DOC_FIELDS, docs)
    if doc_id in locks:
        remain = [r for r in _read_csv(vault / "正式" / "锁.csv", LOCK_FIELDS) if r.get("doc_id") != doc_id]
        _write_csv(vault / "正式" / "锁.csv", LOCK_FIELDS, remain)
    write_board(case_id, cases_root, files_root)
    row["actor"] = actor
    return row


def _retire_current_file(vault: Path, doc: dict) -> None:
    doc_id = (doc.get("doc_id") or "").strip()
    if not doc_id:
        return
    current_dir = vault / "正式" / "现行"
    if not current_dir.is_dir():
        return
    rev = doc.get("rev") or "0"
    try:
        dead_dir = vault / "正式" / "失效" / f"v{int(rev):03d}"
    except ValueError:
        dead_dir = vault / "正式" / "失效" / f"v{rev}"
    dead_dir.mkdir(parents=True, exist_ok=True)
    moved = None
    for p in sorted(current_dir.glob(f"{doc_id}.*")):
        dest = dead_dir / p.name
        if dest.exists():
            dest = dead_dir / f"{p.stem}_{now().replace(':', '')}{p.suffix}"
        shutil.move(str(p), str(dest))
        moved = dest
        p.write_text(
            f"已失效（CHANGE rewind）。原件已移至 正式/失效/。勿当现行。\n"
            f"doc_id={doc_id} rev={rev}\n",
            encoding="utf-8",
        )
    if moved is not None:
        try:
            doc["path"] = str(moved.resolve().relative_to(ROOT))
        except ValueError:
            doc["path"] = str(moved)


def invalidate_from(case_id: str, stages: list[str], cases_root: Path | None = None, files_root: Path | None = None) -> None:
    vault = vault_path(case_id, cases_root, files_root)
    if not (vault / "正式" / "清单.csv").is_file():
        return
    docs = _docs(vault)
    stage_set = set(stages)
    changed = False
    for d in docs:
        if d.get("stage") in stage_set and d.get("status") == "现行":
            d["status"] = "invalidated"
            _retire_current_file(vault, d)
            changed = True
    if changed:
        _write_csv(vault / "正式" / "清单.csv", DOC_FIELDS, docs)
        write_board(case_id, cases_root, files_root)
    roots = []
    if cases_root is not None:
        roots.append(Path(cases_root) / case_id / "measure" / "出数")
    roots.append(Path(__file__).resolve().parents[1] / "流程" / "03 测量" / "案件" / case_id / "出数")
    for d in roots:
        if d.is_dir():
            _invalidate_measure_evidence(d)


def _invalidate_measure_evidence(out_dir: Path) -> None:
    import sys

    tools = str(ROOT / "流程" / "03 测量" / "工具")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import metrics_rollup

    metrics_rollup.invalidate_evidence(out_dir)


def promote_stage_outputs(
    state: dict,
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> list[dict]:
    case_id = state["case_id"]
    stage = state["stage"]
    gate = {
        "01": "G0",
        "02": "G1",
        "07": "G6",
        "08": "G7",
        "03": "G3",
        "04": "G2",
        "05": "G5",
        "06": "G4",
        "09": "G8",
    }.get(stage, "")
    out_dir = (cases_root or DEFAULT_CASES) / case_id / "out"
    if not out_dir.is_dir():
        return []
    vault = init_vault(case_id, cases_root, files_root)
    current = {d["doc_id"]: d for d in _docs(vault) if d.get("status") == "现行"}
    candidates: list[Path] = []
    staged = out_dir / stage
    if staged.is_dir():
        candidates.extend(p for p in staged.iterdir() if p.is_file() and not p.name.startswith("."))
    for p in out_dir.iterdir():
        if p.is_file() and not p.name.startswith(".") and p.name.startswith(stage + "_"):
            candidates.append(p)
    done: list[dict] = []
    for p in sorted(candidates, key=lambda x: x.name):
        doc_id = p.stem
        prev = current.get(doc_id)
        if prev and prev.get("checksum") == _sha256(p):
            continue
        if prev and prev.get("stage") != stage:
            continue
        done.append(
            promote_formal(
                case_id,
                p,
                doc_id=doc_id,
                gate=gate,
                stage=stage,
                title=p.stem,
                cases_root=cases_root,
                files_root=files_root,
            )
        )
    return done


def checkout(
    case_id: str,
    doc_id: str,
    member: str,
    note: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    doc_id = _require_doc_id(doc_id)
    member = member.strip()
    if not member:
        _fail("member required")
    vault = init_vault(case_id, cases_root, files_root)
    docs = [d for d in _docs(vault) if d.get("doc_id") == doc_id and d.get("status") == "现行"]
    if not docs:
        _fail(f"no current {doc_id}")
    locks = _locks(vault)
    if doc_id in locks and locks[doc_id]["member"] != member:
        _fail(f"{doc_id} locked by {locks[doc_id]['member']}")
    row = {"doc_id": doc_id, "member": member, "at": now(), "note": note}
    others = [r for r in _read_csv(vault / "正式" / "锁.csv", LOCK_FIELDS) if r.get("doc_id") != doc_id]
    others.append(row)
    _write_csv(vault / "正式" / "锁.csv", LOCK_FIELDS, others)
    write_board(case_id, cases_root, files_root)
    return row


def checkin(
    case_id: str,
    doc_id: str,
    src: str | Path,
    member: str,
    gate: str = "",
    stage: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    return promote_formal(
        case_id,
        src,
        doc_id,
        gate=gate,
        stage=stage,
        member=member,
        actor=member,
        cases_root=cases_root,
        files_root=files_root,
    )


def drop_exchange(
    case_id: str,
    src: str | Path,
    sender: str,
    receiver: str,
    note: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    src_p = Path(src)
    if not src_p.is_file():
        _fail(f"no file {src_p}")
    sender, receiver = sender.strip(), receiver.strip()
    if not sender or not receiver:
        _fail("sender and receiver required")
    vault = init_vault(case_id, cases_root, files_root)
    n = len(_read_csv(vault / "中转" / "往来.csv", XFER_FIELDS)) + 1
    item_id = f"X{n:04d}"
    dest = vault / "中转" / "收件" / f"{item_id}_{_safe(src_p.name)}"
    shutil.copy2(src_p, dest)
    row = {
        "item_id": item_id,
        "at": now(),
        "action": "drop",
        "sender": sender,
        "receiver": receiver,
        "filename": dest.name,
        "checksum": _sha256(dest),
        "status": "待取",
        "note": note,
    }
    _append_csv(vault / "中转" / "往来.csv", XFER_FIELDS, row)
    write_board(case_id, cases_root, files_root)
    return row


def _xfer_latest(vault: Path, item_id: str) -> dict:
    rows = [r for r in _read_csv(vault / "中转" / "往来.csv", XFER_FIELDS) if r.get("item_id") == item_id]
    if not rows:
        _fail(f"no item {item_id}")
    return rows[-1]


def pick_exchange(
    case_id: str,
    item_id: str,
    member: str,
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    vault = init_vault(case_id, cases_root, files_root)
    last = _xfer_latest(vault, item_id)
    if last["status"] != "待取":
        _fail(f"{item_id} status {last['status']}, not 待取")
    if last["receiver"] != member:
        _fail(f"{item_id} is for {last['receiver']}, not {member}")
    src = vault / "中转" / "收件" / last["filename"]
    dest_dir = vault / "中转" / "待取" / member
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / last["filename"]
    if src.is_file():
        shutil.move(str(src), str(dest))
    row = dict(last)
    row.update({"at": now(), "action": "pick", "status": "已领取", "filename": dest.name})
    _append_csv(vault / "中转" / "往来.csv", XFER_FIELDS, row)
    write_board(case_id, cases_root, files_root)
    return row


def ack_exchange(
    case_id: str,
    item_id: str,
    member: str,
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    vault = init_vault(case_id, cases_root, files_root)
    last = _xfer_latest(vault, item_id)
    if last["status"] not in {"已领取", "待取"}:
        _fail(f"{item_id} already {last['status']}")
    if last["receiver"] != member:
        _fail(f"{item_id} is for {last['receiver']}, not {member}")
    src_candidates = [
        vault / "中转" / "待取" / member / last["filename"],
        vault / "中转" / "收件" / last["filename"],
    ]
    dest = vault / "中转" / "已取" / last["filename"]
    for src in src_candidates:
        if src.is_file():
            shutil.move(str(src), str(dest))
            break
    row = dict(last)
    row.update({"at": now(), "action": "ack", "status": "已取"})
    _append_csv(vault / "中转" / "往来.csv", XFER_FIELDS, row)
    write_board(case_id, cases_root, files_root)
    return row


def board(case_id: str, cases_root: Path | None = None, files_root: Path | None = None) -> dict:
    vault = init_vault(case_id, cases_root, files_root)
    xf = _read_csv(vault / "中转" / "往来.csv", XFER_FIELDS)
    latest: dict[str, dict] = {}
    for r in xf:
        latest[r["item_id"]] = r
    pending = [r for r in latest.values() if r.get("status") in {"待取", "已领取"}]
    current = [d for d in _docs(vault) if d.get("status") == "现行"]
    locks = list(_locks(vault).values())
    return {
        "case_id": case_id,
        "vault": str(vault),
        "pending": pending,
        "current_docs": current,
        "locks": locks,
        "raw_count": len(_read_csv(vault / "原始" / "登记.csv", RAW_FIELDS)),
        "public": public_paths(case_id),
    }


def format_board(b: dict) -> str:
    lines = [
        f"# 中转看板（{b['case_id']}）",
        f"更新：{now()}",
        "",
        "## 待取 / 已领取（先处理这些）",
    ]
    if not b["pending"]:
        lines.append("无。")
    else:
        for r in b["pending"]:
            lines.append(
                f"- `{r['item_id']}` {r['status']}　{r['sender']} → {r['receiver']}　`{r['filename']}`　{r.get('note', '')}"
            )
    lines += ["", "## 正式现行（改之前先 checkout）"]
    if not b["current_docs"]:
        lines.append("尚无已发布正式文件。")
    else:
        for d in b["current_docs"]:
            lines.append(f"- `{d['doc_id']}` r{d['rev']}　门 {d.get('gate') or '—'}　{d.get('title')}")
    lines += ["", "## 签出锁"]
    if not b["locks"]:
        lines.append("无锁。")
    else:
        for r in b["locks"]:
            lines.append(f"- `{r['doc_id']}` 由 {r['member']} 锁住　{r.get('note', '')}")
    pub = b.get("public") or {}
    lines += [
        "",
        "## 路径",
        f"- 原始：`{pub.get('raw', '')}`",
        f"- 正式现行：`{pub.get('formal', '')}`",
        f"- 中转收件：`{pub.get('inbox_xfer', '')}`",
        f"- 原始条数：{b.get('raw_count', 0)}",
        "",
    ]
    return "\n".join(lines)


def write_board(case_id: str, cases_root: Path | None = None, files_root: Path | None = None) -> Path:
    vault = vault_path(case_id, cases_root, files_root)
    b = board(case_id, cases_root, files_root)
    path = vault / "中转" / "看板.md"
    path.write_text(format_board(b) + "\n", encoding="utf-8")
    (vault / "中转" / "board.json").write_text(json.dumps(b, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
