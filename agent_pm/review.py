#!/usr/bin/env python3
"""门前质检流程。硬规则由引擎算；五项质量分由 Agent 打，引擎只算结果。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import engine
import files
import teaching

QUALITY_DIMS = (
    "completeness",
    "correctness",
    "consistency",
    "traceability",
    "executability",
)
PASS_MIN_SUM = 8
CONF_FLOOR = 0.80
SOFT_OK = frozenset({"PASS", "OVERRIDE_SOFT"})
BLOCK_APPLY = frozenset({"rework_required", "appeal_pending"})
REVIEW_OK = frozenset({"onboarding", "material_pending", "agent_review", "rework_required", "agent_draft"})
APPEAL_OK = frozenset({"rework_required"})
RESOLVE_OK = frozenset({"appeal_pending"})


def review_engaged(state: dict) -> bool:
    teaching.ensure_process(state)
    if state.get("profiles"):
        return True
    rev = state.get("review") or {}
    if rev.get("current_id") or rev.get("current_result"):
        return True
    return state.get("activity") in BLOCK_APPLY | {"agent_review"}


def stage_allows_apply(state: dict) -> bool:
    teaching.ensure_process(state)
    rev = state["review"]
    if state.get("activity") in BLOCK_APPLY:
        return False
    if state.get("activity") not in {"agent_draft", "human_gate"}:
        return False
    return rev.get("current_stage") == state.get("stage") and rev.get("current_result") in SOFT_OK


def ui_band(hard_ok: bool, quality: dict) -> str:
    vals = [int(quality.get(k, 0)) for k in QUALITY_DIMS]
    if not hard_ok or any(v == 0 for v in vals) or sum(vals) < PASS_MIN_SUM:
        return "不合格"
    if sum(vals) >= 10:
        return "合格"
    return "基本合格"


def parse_confidence(val: object) -> float:
    try:
        conf = float(val)
    except (TypeError, ValueError):
        engine._fail("confidence must be a finite number in 0..1")
    if not math.isfinite(conf) or conf < 0.0 or conf > 1.0:
        engine._fail("confidence must be a finite number in 0..1")
    return conf


def compute_result(hard_fails: list, quality: dict, confidence: float) -> str:
    if hard_fails:
        return "REWORK"
    vals = []
    for key in QUALITY_DIMS:
        if key not in quality:
            engine._fail(f"quality missing {key}")
        try:
            n = int(quality[key])
        except (TypeError, ValueError):
            engine._fail(f"quality {key} must be 0, 1 or 2")
        if n not in (0, 1, 2):
            engine._fail(f"quality {key} must be 0, 1 or 2")
        vals.append(n)
    conf = parse_confidence(confidence)
    if conf < CONF_FLOOR:
        return "HUMAN_REVIEW_REQUIRED"
    if any(v == 0 for v in vals) or sum(vals) < PASS_MIN_SUM:
        return "REWORK"
    return "PASS"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_activity(state: dict, allowed: frozenset[str], op: str) -> None:
    teaching.ensure_process(state)
    if state.get("waiting") == "done" or state.get("activity") == "done":
        engine._fail(f"{op} not allowed when case is done")
    act = state.get("activity") or "onboarding"
    if act not in allowed:
        engine._fail(f"{op} not allowed from activity {act}")


def _load_raw(
    case_id: str, raw_id: str, cases_root: Path | None, files_root: Path | None
) -> tuple[dict | None, str, str, bool]:
    if not raw_id:
        return None, "", "", False
    vault = files.vault_path(case_id, cases_root, files_root)
    rows = files._read_csv(vault / "原始" / "登记.csv", files.RAW_FIELDS)
    row = next((r for r in rows if r.get("raw_id") == raw_id), None)
    if row is None:
        return None, "", "", False
    stage = row.get("stage") or ""
    name = row.get("filename") or ""
    path = vault / "原始" / stage / name
    if not path.is_file():
        iso = vault / "原始" / stage / "隔离" / name
        path = iso if iso.is_file() else path
    if not path.is_file():
        return row, "", "", False
    data = path.read_bytes()
    live = _sha(data)
    registered = (row.get("checksum") or "").strip()
    tampered = bool(registered) and live != registered
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    return row, text, live, tampered


def _find_draft_path(case_id: str, draft_id: str, cases_root: Path | None, files_root: Path | None) -> Path | None:
    names = {draft_id, Path(draft_id).name}
    stems = {Path(draft_id).stem}
    dirs: list[Path] = []
    if cases_root is not None:
        dirs.append(Path(cases_root) / case_id / "out")
    dirs.append(engine.DEFAULT_CASES / case_id / "out")
    vault = files.vault_path(case_id, cases_root, files_root)
    dirs.append(vault / "正式" / "现行")
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and (p.name in names or p.stem in stems):
                return p
    return None


def _load_draft(
    case_id: str,
    draft_id: str,
    checksum: str,
    cases_root: Path | None,
    files_root: Path | None,
) -> tuple[dict | None, str, str, bool]:
    if not draft_id or not checksum:
        return None, "", "", False
    path = _find_draft_path(case_id, draft_id, cases_root, files_root)
    if path is None:
        return None, "", "", False
    data = path.read_bytes()
    live = _sha(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    row = {"draft_id": draft_id, "filename": path.name, "kind": "draft"}
    return row, text, live, live != checksum


def _prev_gates_ok(state: dict) -> list[str]:
    stage = state["stage"]
    if stage not in engine.STAGES:
        return ["stage"]
    idx = engine.STAGES.index(stage)
    miss = []
    for prev in engine.STAGES[:idx]:
        gate = engine.GATE_AFTER[prev]
        verdict = (state.get("gates") or {}).get(gate, {}).get("verdict")
        if verdict == "APPROVE":
            continue
        if prev == "05" and verdict == "N/A":
            continue
        miss.append(gate)
    return miss


def _fail_item(state: dict, rule: str, why: str, fix: str, raw_row: dict | None = None, field: str = "") -> dict:
    stage = state["stage"]
    return {
        "rule": rule,
        "raw_id": (raw_row or {}).get("raw_id") or (raw_row or {}).get("draft_id") or "",
        "file": (raw_row or {}).get("filename", ""),
        "field": field,
        "why": why,
        "fix": fix,
        "resubmit": f"agent_pm/cases/{state['case_id']}/inbox/{stage}/",
    }


def hard_rule_failures(
    state: dict,
    payload: dict,
    *,
    raw_row: dict | None = None,
    raw_text: str = "",
    cases_root: Path | None = None,
    target_missing: bool = False,
    tampered: bool = False,
) -> list[dict]:
    fails: list[dict] = []
    stage = state["stage"]
    fields = dict(payload.get("fields") or {})
    texts = [raw_text]
    texts.extend(str(v) for v in fields.values())
    blob = "\n".join(texts)

    if target_missing:
        fails.append(
            _fail_item(
                state,
                "required_materials",
                "没有可审材料：必须绑定已入库 raw_id，或 draft_id+checksum",
                "先 deposit / 写草稿，再带 review_target 提交",
                raw_row,
            )
        )
    if tampered:
        rule = "raw_tampered" if (raw_row or {}).get("raw_id") else "draft_tampered"
        fails.append(
            _fail_item(
                state,
                rule,
                "材料文件哈希与登记/声明的 checksum 不一致，不能按当时版本复核",
                "不要改已入库文件；重新 deposit 或重写草稿后再审",
                raw_row,
            )
        )

    for bad in engine.BANNED_CLAIMS:
        if bad in blob:
            fails.append(
                _fail_item(
                    state,
                    "banned",
                    f"禁售句「{bad}」不能过当前门 {engine.GATE_AFTER.get(stage, '')}",
                    "删掉或改成可观察、不保证效果的表述",
                    raw_row,
                )
            )

    miss_gates = _prev_gates_ok(state)
    if miss_gates:
        fails.append(
            _fail_item(
                state,
                "stage_order",
                "上一门还没批，不能在本步交材料：" + ",".join(miss_gates),
                "回到未批的门，先走完再提交",
                raw_row,
            )
        )

    if payload.get("materials_present") is False:
        fails.append(
            _fail_item(
                state,
                "required_materials",
                "必填材料缺失，不能进起草",
                "按 guide 的材料路径补齐后再提交",
                raw_row,
            )
        )

    if raw_row and raw_row.get("raw_id"):
        raw_stage = raw_row.get("stage") or ""
        if raw_stage and raw_stage != stage:
            fails.append(
                _fail_item(
                    state,
                    "material_path",
                    f"材料属于 {raw_stage}，当前是 {stage}",
                    f"把文件存到 原始/{stage}/ 或当前 inbox/{stage}/",
                    raw_row,
                )
            )

    sop = state["fields"].get("sop_stage") or fields.get("sop_stage") or state["fields"].get("sop_stage_intent") or ""
    if "sop_stage" in fields and stage == "02":
        intent = state["fields"].get("sop_stage_intent") or fields.get("sop_stage")
        locked = fields["sop_stage"]
        if locked not in engine.VERDICT_OK:
            fails.append(_fail_item(state, "field_legal", f"sop_stage={locked} 不在允许集", "只能写 诊断 / 冲刺 / 续约", raw_row, "sop_stage"))
        elif intent and locked != intent and locked not in engine.NARROW.get(intent, ()):
            fails.append(
                _fail_item(state, "cross_stage", f"不能从 {intent} 加宽到 {locked}", "保持意向产品线或只允许收窄", raw_row, "sop_stage")
            )
    if stage == "07" and sop == "诊断":
        scope = str(fields.get("budget_scope") or state["fields"].get("budget_scope") or "")
        if any(tok in scope for tok in engine.DIAG_BUDGET_BAN):
            fails.append(
                _fail_item(state, "cross_stage", "诊断预算不能含干预/一类证据/改页", "范围改成冻结+噪声+基线+抽检", raw_row, "budget_scope")
            )
    if fields.get("verdict_4"):
        v = fields["verdict_4"]
        if sop and v not in engine.VERDICT_OK.get(sop, ()):
            fails.append(_fail_item(state, "field_legal", f"{v} 超出 {sop} 允许集", "改成当前产品线允许的四选一", raw_row, "verdict_4"))
        prior = state["fields"].get("verdict_4")
        if stage in {"06", "09"} and prior and v != prior:
            fails.append(_fail_item(state, "cross_stage", "验收/结项四选一必须与已锁值一致", f"改回 {prior}", raw_row, "verdict_4"))
    if stage == "03" and fields.get("freeze_id") and cases_root is not None:
        if not engine.freeze_exists(str(fields.get("freeze_id") or ""), state.get("case_id") or "", cases_root):
            fails.append(
                _fail_item(
                    state,
                    "evidence",
                    "本案没有对应冻结目录，不能过 G3",
                    "先 freeze_config --case-id，不要用共享冻结",
                    raw_row,
                    "freeze_id",
                )
            )
    return fails


def _issue_from_fail(item: dict) -> dict:
    return {
        "raw_id": item.get("raw_id", ""),
        "file": item.get("file", ""),
        "field": item.get("field", ""),
        "line": item.get("line", ""),
        "why": item.get("why", ""),
        "fix": item.get("fix", ""),
        "resubmit": item.get("resubmit", ""),
        "hard": True,
    }


def _normalize_issues(raw: object, raw_id: str) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "raw_id": item.get("raw_id") or raw_id,
                "file": item.get("file") or "",
                "field": item.get("field") or "",
                "line": item.get("line") or "",
                "why": item.get("why") or "",
                "fix": item.get("fix") or "",
                "resubmit": item.get("resubmit") or "",
                "hard": False,
            }
        )
    return out


def review_dir(case_id: str, stage: str, cases_root: Path | None = None, files_root: Path | None = None) -> Path:
    vault = files.init_vault(case_id, cases_root, files_root)
    d = vault / "原始" / stage / "评审"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_id(state: dict) -> str:
    teaching.ensure_process(state)
    state["review"]["seq"] = int(state["review"].get("seq") or 0) + 1
    return f"QR{state['review']['seq']:04d}"


def _human_conclusion(rec: dict) -> str:
    result = rec.get("result") or ""
    resolution = rec.get("resolution") or {}
    if resolution.get("verdict") == "OVERRIDE_SOFT" or result == "OVERRIDE_SOFT":
        return "人工已接受软性判断（OVERRIDE_SOFT），可继续起草，仍须人批准过门"
    if resolution.get("verdict") == "UPHOLD":
        return "人工维持打回（UPHOLD）"
    if result == "HUMAN_REVIEW_REQUIRED":
        return "需人工复核（不是打回）"
    if result == "REWORK":
        return "不合格，需要修改后重交"
    if result == "PASS":
        return rec.get("ui_band") or "合格"
    return rec.get("ui_band") or result


def format_review_md(rec: dict) -> str:
    target = rec.get("raw_id") or rec.get("draft_id") or "（无）"
    kind = rec.get("target_kind") or ("raw" if rec.get("raw_id") else "draft" if rec.get("draft_id") else "")
    lines = [
        f"# 评审 {rec['review_id']}",
        f"阶段：{rec['stage']}　对象：{kind} {target}　checksum：{rec.get('input_checksum') or ''}",
        "",
        "## 结论",
        f"- 对人：{_human_conclusion(rec)}",
        f"- 引擎结果：{rec.get('result') or ''}",
        f"- 质量档：{rec.get('ui_band') or ''}",
        f"- 置信度：{rec.get('confidence')}",
    ]
    resolution = rec.get("resolution") or {}
    if resolution:
        lines.append(f"- 最终复核：{resolution.get('verdict')}　理由：{resolution.get('reason') or ''}")
    else:
        lines.append("- 最终复核：尚未裁决")
    lines += ["", "## 需要改的地方"]
    issues = rec.get("issues") or []
    if not issues:
        lines.append("无。")
    else:
        for i, item in enumerate(issues, 1):
            lines.append(f"{i}. {item.get('why') or ''}")
            if item.get("fix"):
                lines.append(f"   改法：{item['fix']}")
            if item.get("resubmit"):
                lines.append(f"   再交到：`{item['resubmit']}`")
            loc = " / ".join(x for x in (item.get("raw_id"), item.get("file"), item.get("field"), str(item.get("line") or "")) if x)
            if loc:
                lines.append(f"   对着：{loc}")
    if rec.get("coaching"):
        lines += ["", "## 升级辅导", rec["coaching"].get("ask") or "一次只补一个缺失事实，不要编造。"]
    lines += ["", "Agent 不能替你批准。硬规则不能申诉。"]
    return "\n".join(lines) + "\n"


def _resolve_target(
    state: dict,
    payload: dict,
    raw_id: str,
    cases_root: Path | None,
    files_root: Path | None,
) -> tuple[dict | None, str, str, bool, str, str]:
    target = dict(payload.get("review_target") or {})
    raw_id = raw_id or str(payload.get("raw_id") or target.get("raw_id") or "")
    draft_id = str(payload.get("draft_id") or target.get("draft_id") or "")
    draft_ck = str(payload.get("draft_checksum") or target.get("checksum") or "")
    if raw_id:
        row, text, digest, tampered = _load_raw(state["case_id"], raw_id, cases_root, files_root)
        missing = row is None
        return row, text, digest, tampered, raw_id, "raw" if not missing else "raw"
    if draft_id:
        row, text, digest, tampered = _load_draft(state["case_id"], draft_id, draft_ck, cases_root, files_root)
        return row, text, digest, tampered, draft_id, "draft"
    return None, "", "", False, "", ""


def submit_review(
    state: dict,
    payload: dict,
    member: str = "",
    raw_id: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
) -> dict:
    teaching.ensure_process(state)
    _require_activity(state, REVIEW_OK, "review")
    member = (member or state.get("current_member") or "").strip()
    raw_row, raw_text, digest, tampered, target_id, target_kind = _resolve_target(
        state, payload, raw_id, cases_root, files_root
    )
    target_missing = not target_kind or (target_kind == "raw" and raw_row is None) or (target_kind == "draft" and raw_row is None)
    if target_kind == "draft" and not str(payload.get("draft_checksum") or (payload.get("review_target") or {}).get("checksum") or ""):
        target_missing = True
    hard = hard_rule_failures(
        state,
        payload,
        raw_row=raw_row,
        raw_text=raw_text,
        cases_root=cases_root,
        target_missing=target_missing,
        tampered=tampered,
    )
    quality = dict(payload.get("quality") or {})
    confidence = parse_confidence(payload.get("confidence", 1))
    result = compute_result(hard, quality, confidence)
    claimed = payload.get("result")
    facts_missing = [str(x).strip() for x in (payload.get("facts_missing") or []) if str(x).strip()]
    fields = dict(payload.get("fields") or {})
    for key in facts_missing:
        val = str(fields.get(key) or "").strip()
        if val and val != "待确认":
            engine._fail(f"cannot invent missing fact {key}")
    stage = state["stage"]
    attempts = state["review"]["attempts"]
    failures = state["review"]["failures"]
    n = int(attempts.get(stage) or 0) + 1
    attempts[stage] = n
    first_attempt = n == 1
    if result == "REWORK":
        failures[stage] = int(failures.get(stage) or 0) + 1
    fail_n = int(failures.get(stage) or 0)
    rid = _next_id(state)
    bind_id = (raw_row or {}).get("raw_id") or (raw_row or {}).get("draft_id") or target_id
    issues = [_issue_from_fail(x) for x in hard] + _normalize_issues(payload.get("issues"), bind_id)
    issues.sort(key=lambda x: (not x.get("hard"), x.get("why") or ""))
    coaching = None
    if result == "REWORK" and fail_n >= 3:
        ask = ""
        if facts_missing:
            ask = f"只问这一项：{facts_missing[0]} 的事实是什么？答完再说下一项。"
        elif issues:
            ask = issues[0].get("fix") or issues[0].get("why") or "一次只改当前最挡住门的一项。"
        else:
            ask = "一次只补一个缺失事实。没有事实就写待确认，不要编。"
        coaching = {"mode": "one_fact", "ask": ask, "invented": False}
    if target_missing:
        digest = ""
    rec = {
        "review_id": rid,
        "rule_version": str(payload.get("rule_version") or teaching.load_config()["version"]),
        "case_id": state["case_id"],
        "stage": stage,
        "member": member,
        "target_kind": target_kind,
        "raw_id": (raw_row or {}).get("raw_id") or "",
        "draft_id": (raw_row or {}).get("draft_id") or "",
        "input_checksum": digest,
        "claimed_result": claimed or "",
        "result": result,
        "ui_band": ui_band(not hard, quality),
        "hard_fails": hard,
        "quality": {k: int(quality.get(k, 0)) for k in QUALITY_DIMS},
        "confidence": confidence,
        "issues": issues,
        "facts_missing": facts_missing,
        "coaching": coaching,
        "attempt": n,
        "failure_count": fail_n,
        "at": engine.now(),
    }
    dest = review_dir(state["case_id"], stage, cases_root, files_root)
    (dest / f"{rid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / f"{rid}.md").write_text(format_review_md(rec), encoding="utf-8")
    state["review"]["current_id"] = rid
    state["review"]["current_result"] = result
    state["review"]["current_stage"] = stage
    state["review"]["current_checksum"] = digest
    if result == "PASS":
        state["activity"] = "agent_draft"
        state["waiting"] = "agent"
    elif result == "HUMAN_REVIEW_REQUIRED":
        state["activity"] = "appeal_pending"
        state["waiting"] = "human"
    else:
        state["activity"] = "rework_required"
        state["waiting"] = "agent"
    if member:
        teaching.note_review_outcome(state, member, result, first_attempt)
    state["log"].append({"at": engine.now(), "op": "review", "id": rid, "result": result, "attempt": n, "failures": fail_n})
    return rec


def _lock_current(
    state: dict,
    rec: dict,
    review_id: str,
    expected_current_id: str | None = None,
    expected_checksum: str | None = None,
) -> None:
    cur = state["review"]
    if review_id != (cur.get("current_id") or ""):
        engine._fail("not the current review")
    if rec.get("stage") != state.get("stage"):
        engine._fail("review stage mismatch")
    if expected_current_id and expected_current_id != review_id:
        engine._fail("expected_current_id mismatch")
    if expected_checksum and expected_checksum != rec.get("input_checksum"):
        engine._fail("review checksum mismatch")
    if (cur.get("current_checksum") or "") != (rec.get("input_checksum") or ""):
        engine._fail("review is stale")


def _event_paths(dest: Path, review_id: str, kind: str) -> tuple[Path, Path]:
    n = 1
    while (dest / f"{review_id}.{kind}.{n:03d}.json").exists():
        n += 1
    return dest / f"{review_id}.{kind}.{n:03d}.json", dest / f"{review_id}.{kind}.{n:03d}.md"


def _write_event(dest: Path, review_id: str, kind: str, event: dict) -> dict:
    jp, mp = _event_paths(dest, review_id, kind)
    jp.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(format_review_md(event), encoding="utf-8")
    event["event_file"] = jp.name
    return event


def appeal(
    state: dict,
    review_id: str,
    reason: str,
    cases_root: Path | None = None,
    files_root: Path | None = None,
    expected_current_id: str | None = None,
    expected_checksum: str | None = None,
) -> dict:
    teaching.ensure_process(state)
    _require_activity(state, APPEAL_OK, "appeal")
    if not (reason or "").strip():
        engine._fail("appeal needs reason")
    rec = _read_review(state, review_id, cases_root, files_root)
    _lock_current(state, rec, review_id, expected_current_id, expected_checksum)
    if rec.get("hard_fails"):
        engine._fail("hard rules cannot be appealed")
    if rec.get("result") not in {"REWORK", "HUMAN_REVIEW_REQUIRED"}:
        engine._fail("only soft rework can be appealed")
    event = {
        **rec,
        "event": "appeal",
        "appeal": {"reason": reason.strip(), "at": engine.now()},
    }
    dest = _review_path(state, review_id, cases_root, files_root).parent
    _write_event(dest, review_id, "appeal", event)
    state["activity"] = "appeal_pending"
    state["waiting"] = "human"
    state["log"].append({"at": engine.now(), "op": "appeal", "id": review_id})
    return event


def resolve_review(
    state: dict,
    review_id: str,
    verdict: str,
    actor: str = "human",
    reason: str = "",
    cases_root: Path | None = None,
    files_root: Path | None = None,
    expected_current_id: str | None = None,
    expected_checksum: str | None = None,
) -> dict:
    teaching.ensure_process(state)
    _require_activity(state, RESOLVE_OK, "resolve-review")
    if actor != "human":
        engine._fail("only human may resolve review")
    if verdict not in {"UPHOLD", "OVERRIDE_SOFT"}:
        engine._fail("verdict must be UPHOLD or OVERRIDE_SOFT")
    if not (reason or "").strip():
        engine._fail("resolve-review needs reason")
    rec = _read_review(state, review_id, cases_root, files_root)
    _lock_current(state, rec, review_id, expected_current_id, expected_checksum)
    if rec.get("hard_fails") and verdict == "OVERRIDE_SOFT":
        engine._fail("hard rules cannot be overridden")
    resolution = {"verdict": verdict, "actor": actor, "reason": reason.strip(), "at": engine.now()}
    if verdict == "OVERRIDE_SOFT":
        new_result = "OVERRIDE_SOFT"
        state["review"]["current_result"] = "OVERRIDE_SOFT"
        state["activity"] = "agent_draft"
        state["waiting"] = "agent"
    else:
        new_result = "REWORK"
        state["review"]["current_result"] = "REWORK"
        state["activity"] = "rework_required"
        state["waiting"] = "agent"
    event = {
        **rec,
        "event": "resolve",
        "result": new_result,
        "resolution": resolution,
    }
    dest = _review_path(state, review_id, cases_root, files_root).parent
    _write_event(dest, review_id, "resolve", event)
    state["log"].append({"at": engine.now(), "op": "resolve-review", "id": review_id, "verdict": verdict})
    return event


def _review_path(state: dict, review_id: str, cases_root: Path | None, files_root: Path | None) -> Path:
    stage = state.get("stage") or "01"
    p = review_dir(state["case_id"], stage, cases_root, files_root) / f"{review_id}.json"
    if p.is_file():
        return p
    vault = files.vault_path(state["case_id"], cases_root, files_root)
    for found in vault.glob(f"原始/*/评审/{review_id}.json"):
        return found
    engine._fail(f"no review {review_id}")
    raise AssertionError("unreachable")


def _read_review(state: dict, review_id: str, cases_root: Path | None, files_root: Path | None) -> dict:
    return json.loads(_review_path(state, review_id, cases_root, files_root).read_text(encoding="utf-8"))


def reset_stage_review(state: dict) -> None:
    teaching.ensure_process(state)
    state["review"]["current_id"] = ""
    state["review"]["current_result"] = ""
    state["review"]["current_checksum"] = ""
    state["review"]["current_stage"] = state.get("stage") or ""
    if state.get("profiles"):
        state["activity"] = "material_pending"
    else:
        state["activity"] = "onboarding"
    for rec in (state.get("profiles") or {}).values():
        rec["stage_novice"] = False
