#!/usr/bin/env python3
"""Agent 驱动的 01→09 全流程状态机。人只通过 decide() 开关门。"""
# 行走：01→02→07→08→03→04→05→06→09。only human may APPROVE。

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).resolve().parent / "cases"
FIELDS_CSV = ROOT / "合同" / "核心合同字段.csv"

# 文件夹编号是标签；行走顺序是全流程，不是 01–06 核心链再加支撑。
# 预算、沟通必须在测量前锁定；收尾必须在交付后关门。
STAGES = ("01", "02", "07", "08", "03", "04", "05", "06", "09")
GATE_AFTER = {
    "01": "G0",
    "02": "G1",
    "07": "G6",
    "08": "G7",
    "03": "G3",
    "04": "G2",
    "05": "G5",
    "06": "G4",
    "09": "G8",
}
AGENT_PROMPT = {
    "01": "agent_pm/agents/01_intake.md",
    "02": "agent_pm/agents/02_requirements.md",
    "07": "agent_pm/agents/07_budget.md",
    "08": "agent_pm/agents/08_comms.md",
    "03": "agent_pm/agents/03_measure.md",
    "04": "agent_pm/agents/04_plan.md",
    "05": "agent_pm/agents/05_control.md",
    "06": "agent_pm/agents/06_deliver.md",
    "09": "agent_pm/agents/09_close.md",
}
STAGE_FOLDER = {
    "01": "流程/01 客户初次洽谈",
    "02": "流程/02 需求文档",
    "07": "流程/07 预算和资源管理",
    "08": "流程/08 沟通",
    "03": "流程/03 测量",
    "04": "流程/04 项目计划",
    "05": "流程/05 推进实施控制",
    "06": "流程/06 交付物",
    "09": "流程/09 收尾",
}
VERDICT_OK = {
    "诊断": frozenset({"描述基线", "不能下结论"}),
    "冲刺": frozenset({"受控前后描述", "确认性 L1", "不能下结论"}),
    "续约": frozenset({"不能下结论"}),
}
NARROW = {"诊断": frozenset(), "冲刺": frozenset({"诊断"}), "续约": frozenset({"诊断"})}
STAGE_WINDOWS = {
    "诊断": frozenset({"noise", "baseline"}),
    "冲刺": frozenset({"noise", "baseline", "retest", "intervention"}),
    "续约": frozenset({"weekly", "calib"}),
}
BANNED_CLAIMS = (
    "保证推荐",
    "保证会被推荐",
    "报名因此增长",
    "国内可见性",
    "GEO 已证明",
    "已经优化成功",
    "优化后会涨",
)
YES = frozenset({"是", "yes", "true", "1", "Y", "y"})
DIAG_BUDGET_BAN = ("干预", "一类证据", "改页")
REQUIRED = {
    "01": ("vertical", "city", "client_code", "sop_stage_intent", "ban_ack"),
    "02": (
        "project_id",
        "owner",
        "sop_stage",
        "primary_goal",
        "primary_endpoint",
        "causal_claim",
        "control_design",
        "success_rule_diagnosis",
        "success_rule_sprint",
        "success_rule_retain",
        "treat_need_ids",
        "holdout_need_ids",
        "platforms_required",
    ),
    "07": ("budget_hours", "budget_scope", "quote_excludes_l1"),
    "08": ("stakeholder_decision", "comms_cadence", "comms_bound"),
    "03": ("freeze_id", "data_grade", "baseline_verdict_4", "measure_isolated"),
    "04": (),
    "05": ("intervention_class",),
    "06": ("verdict_4",),
    "09": ("close_assets_ok", "close_no_reopen_l1"),
}
MIN_DID_CLUSTERS = 2
FREEZE_ROOT = ROOT / "流程" / "03 测量" / "配置" / "冻结"
MEASURE_CASES = ROOT / "流程" / "03 测量" / "案件"


def load_writers(path: Path = FIELDS_CSV) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            field = (row.get("field") or "").strip()
            stage = (row.get("writer_stage") or "").strip()
            if field and stage:
                out[field] = stage
    out.setdefault("sop_stage_intent", "01")
    return out


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_state(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "stage": "01",
        "waiting": "agent",
        "activity": "onboarding",
        "current_member": "",
        "profiles": {},
        "review": {
            "current_id": "",
            "current_result": "",
            "current_stage": "",
            "current_checksum": "",
            "current_record_checksum": "",
            "seq": 0,
            "attempts": {},
            "failures": {},
        },
        "fields": {},
        "gates": {},
        "log": [{"at": now(), "op": "init"}],
    }


def case_path(case_id: str, cases_root: Path | None = None) -> Path:
    return (cases_root or DEFAULT_CASES) / case_id / "state.json"


def load_state(case_id: str, cases_root: Path | None = None) -> dict:
    p = case_path(case_id, cases_root)
    if not p.is_file():
        raise FileNotFoundError(f"no case {case_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(state: dict, cases_root: Path | None = None) -> Path:
    p = case_path(state["case_id"], cases_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def init_case(case_id: str, cases_root: Path | None = None) -> dict:
    p = case_path(case_id, cases_root)
    if p.exists():
        raise FileExistsError(case_id)
    state = new_state(case_id)
    p = save_state(state, cases_root)
    (p.parent / "inbox").mkdir(exist_ok=True)
    (p.parent / "out").mkdir(exist_ok=True)
    for s in STAGES:
        (p.parent / "inbox" / s).mkdir(exist_ok=True)
        (p.parent / "out" / s).mkdir(exist_ok=True)
    import files as _files

    _files.init_vault(case_id, cases_root)
    return state


def next_action(state: dict) -> dict:
    import guide as _guide

    stage = state["stage"]
    import teaching as _teach

    _teach.ensure_process(state)
    g = _guide.build_guide(state)
    return {
        "case_id": state["case_id"],
        "stage": stage,
        "folder": STAGE_FOLDER.get(stage, stage),
        "waiting": state["waiting"],
        "activity": state.get("activity") or "onboarding",
        "gate": GATE_AFTER[stage] if state["waiting"] == "human" else "",
        "agent_prompt": AGENT_PROMPT[stage],
        "writable_fields": [f for f, s in load_writers().items() if s == stage],
        "human_only": state["waiting"] == "human",
        "guide": g,
        "briefing": _guide.format_guide(g),
    }


def _fail(msg: str) -> None:
    raise ValueError(msg)


def _is_yes(val: object) -> bool:
    return str(val).strip() in YES


def resolve_freeze_dir(freeze_id: str, case_id: str = "", cases_root: Path | None = None) -> Path | None:
    fid = (freeze_id or "").strip()
    if not fid:
        return None
    # 有 case_id 时只认本案冻结。共享 配置/冻结 只给 freeze_config 复制，不能回退。
    if case_id:
        cands = []
        if cases_root is not None:
            cands.append(Path(cases_root) / case_id / "measure" / "冻结" / fid)
        cands.append(MEASURE_CASES / case_id / "冻结" / fid)
        for d in cands:
            if d.is_dir():
                return d
        return None
    shared = FREEZE_ROOT / fid
    return shared if shared.is_dir() else None


def freeze_exists(freeze_id: str, case_id: str = "", cases_root: Path | None = None) -> bool:
    return resolve_freeze_dir(freeze_id, case_id, cases_root) is not None


def _norm_ids(val: object) -> set[str]:
    return {p.strip() for p in str(val or "").replace(",", ";").split(";") if p.strip()}


FREEZE_HASH_FILES = (
    "queries.csv",
    "aliases.csv",
    "facts.csv",
    "owned_sources.csv",
    "platforms.csv",
    "project.csv",
)


def freeze_files_checksum(freeze_path: Path) -> str:
    h = hashlib.sha256()
    for name in FREEZE_HASH_FILES:
        p = Path(freeze_path) / name
        if not p.is_file():
            return ""
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def freeze_contract_errors(freeze_path: Path, fields: dict) -> list[str]:
    proj_p = freeze_path / "project.csv"
    if not proj_p.is_file():
        return ["project.csv"]
    with proj_p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return ["project.csv"]
    proj = {(k or "").lstrip("\ufeff"): v for k, v in rows[0].items()}
    miss = []
    for key in ("project_id", "sop_stage", "city", "vertical", "platforms_required"):
        left, right = str(proj.get(key) or "").strip(), str(fields.get(key) or "").strip()
        if not left or not right or left != right:
            miss.append(key)
    for key in ("treat_need_ids", "holdout_need_ids"):
        left, right = str(proj.get(key) or "").strip(), str(fields.get(key) or "").strip()
        if not left or not right or _norm_ids(left) != _norm_ids(right):
            miss.append(key)
    computed = freeze_files_checksum(freeze_path)
    stated = ""
    ck_p = freeze_path / "checksum.txt"
    if ck_p.is_file():
        stated = ck_p.read_text(encoding="utf-8").strip()
    if not computed or not stated or computed != stated:
        miss.append("checksum")
    return miss


def isolate_measure_case(case_id: str, freeze_id: str, cases_root: Path | None = None) -> Path:
    d = Path(cases_root) / case_id / "measure" if cases_root is not None else MEASURE_CASES / case_id
    (d / "台账").mkdir(parents=True, exist_ok=True)
    (d / "出数").mkdir(parents=True, exist_ok=True)
    (d / "样本").mkdir(parents=True, exist_ok=True)
    (d / "冻结").mkdir(parents=True, exist_ok=True)
    (d / "freeze_id.txt").write_text((freeze_id or "").strip() + "\n", encoding="utf-8")
    readme = d / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# 本案测量运行时（{case_id}）\n\n"
            f"冻结：`{freeze_id}`。台账和出数只写本目录，禁止读写共享 `台账/samples.csv`。\n",
            encoding="utf-8",
        )
    return d


def _owner_for(key: str, stage: str, sop: str) -> str | None:
    writers = load_writers()
    if key == "verdict_4" and sop == "冲刺":
        return "05"
    if key == "verdict_4":
        return "03"
    return writers.get(key)


def _merged_fields(state: dict, incoming: dict, payload: dict) -> dict:
    out = dict(state.get("fields") or {})
    out.update(incoming)
    if "windows" in payload:
        out["windows"] = list(payload["windows"])
    return out


def missing_required(
    state: dict,
    incoming: dict | None = None,
    payload: dict | None = None,
    cases_root: Path | None = None,
) -> list[str]:
    stage = state["stage"]
    fields = _merged_fields(state, incoming or {}, payload or {})
    sop = fields.get("sop_stage") or fields.get("sop_stage_intent") or ""
    need = list(REQUIRED.get(stage, ()))
    if stage == "03" and sop != "冲刺":
        need.append("verdict_4")
    if stage == "05" and sop == "冲刺":
        need.append("verdict_4")
    miss = [k for k in need if not str(fields.get(k) or "").strip()]
    if stage == "04" and not fields.get("windows"):
        miss.append("windows")
    if stage == "01" and not _is_yes(fields.get("ban_ack", "")):
        miss.append("ban_ack")
    if stage == "07":
        try:
            if float(str(fields.get("budget_hours") or "").strip()) <= 0:
                miss.append("budget_hours")
        except ValueError:
            miss.append("budget_hours")
    if stage == "03":
        fd = resolve_freeze_dir(str(fields.get("freeze_id") or ""), state.get("case_id") or "", cases_root)
        if fd is None:
            miss.append("freeze_id")
        else:
            mismatch = freeze_contract_errors(fd, fields)
            if mismatch:
                miss.append("freeze_mismatch")
        if not _is_yes(fields.get("measure_isolated", "")):
            miss.append("measure_isolated")
        bv = fields.get("baseline_verdict_4") or ""
        if bv not in {"描述基线", "不能下结论"}:
            miss.append("baseline_verdict_4")
    return miss


L1_DERIVED = ("did_excludes_zero", "did_positive", "treat_clusters", "holdout_clusters", "coverage_ok")


def _measure_out_dirs(case_id: str, cases_root: Path | None) -> list[Path]:
    out = []
    if cases_root is not None:
        out.append(Path(cases_root) / case_id / "measure" / "出数")
    out.append(MEASURE_CASES / case_id / "出数")
    return out


def _evidence_identity(case_id: str, fields: dict) -> dict:
    ident = {
        "case_id": case_id,
        "project_id": str(fields.get("project_id") or "").strip(),
        "freeze_id": str(fields.get("freeze_id") or "").strip(),
        "config_checksum": str(fields.get("config_checksum") or "").strip(),
    }
    missing = [k for k, v in ident.items() if not v]
    if missing:
        _fail("missing evidence identity in state: " + ",".join(missing))
    return ident


def _row_identity_errors(row: dict, expect: dict, label: str) -> None:
    for key, want in expect.items():
        got = str(row.get(key) or "").strip()
        if not got:
            _fail(f"{label} missing {key}")
        if got != want:
            _fail(f"{label} identity mismatch {key}")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _metrics():
    import sys

    tools = str(ROOT / "流程" / "03 测量" / "工具")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import metrics_rollup

    return metrics_rollup


def evidence_bundle_ok(out_dir: Path, ident: dict) -> bool:
    return _metrics().evidence_bundle_ok(out_dir, ident)


def commit_fresh_evidence(out_dir: Path, ident: dict) -> bool:
    """全部新证据写入且身份校验通过后，才清掉 CHANGE 留下的 INVALIDATED。"""
    return _metrics().publish_evidence(out_dir, ident)


def derive_l1_from_files(case_id: str, fields: dict, cases_root: Path | None = None) -> dict:
    cands = _measure_out_dirs(case_id, cases_root)
    for d in cands:
        if (d / "INVALIDATED.txt").is_file():
            _fail("did.csv invalidated")
    out_dir = None
    for d in cands:
        if (d / "did.csv").is_file():
            out_dir = d
            break
    if out_dir is None:
        _fail("no did.csv")
    did_path = out_dir / "did.csv"
    cov_path = out_dir / "coverage.csv"
    man_path = out_dir / "evidence_manifest.json"
    expect = _evidence_identity(case_id, fields)
    if not man_path.is_file():
        _fail("no evidence_manifest.json")
    ident = json.loads(man_path.read_text(encoding="utf-8"))
    _row_identity_errors(ident, expect, "evidence_manifest")
    files = ident.get("files") or {}
    if "did.csv" not in files:
        _fail("evidence_manifest missing did.csv checksum")
    if files.get("did.csv") != _file_digest(did_path):
        _fail("evidence_manifest checksum mismatch did.csv")
    if cov_path.is_file():
        if "coverage.csv" not in files:
            _fail("evidence_manifest missing coverage.csv checksum")
        if files.get("coverage.csv") != _file_digest(cov_path):
            _fail("evidence_manifest checksum mismatch coverage.csv")
    mr = _metrics()
    did_run = mr.csv_evidence_run_id(did_path)
    cov_run = mr.csv_evidence_run_id(cov_path) if cov_path.is_file() else ""
    man_run = str(ident.get("evidence_run_id") or "").strip()
    if not did_run or did_run != cov_run or did_run != man_run:
        _fail("evidence_run_id mismatch")
    with did_path.open(encoding="utf-8-sig", newline="") as f:
        did_rows = list(csv.DictReader(f))
    mention = [r for r in did_rows if (r.get("metric") or "") == "mention"]
    if not mention:
        _fail("did.csv has no mention rows")
    for r in mention:
        _row_identity_errors(r, expect, "did.csv")
        if (r.get("causal_claim") or "") != "did_isolated":
            _fail("did.csv causal_claim is not did_isolated")
        if (r.get("excludes_zero") or "") != "1":
            _fail("did.csv excludes_zero is not 1")
        try:
            lo = float(r.get("did_lo") or "nan")
        except ValueError:
            lo = float("nan")
        if not (lo > 0):
            _fail("did_lo is not > 0")
        if (r.get("verdict") or "") != "did_excludes_zero":
            _fail("did.csv verdict is not did_excludes_zero")
    try:
        tc = min(int(r.get("n_treat_clusters") or "0") for r in mention)
        hc = min(int(r.get("n_hold_clusters") or "0") for r in mention)
    except ValueError:
        tc, hc = 0, 0
    if tc < MIN_DID_CLUSTERS or hc < MIN_DID_CLUSTERS:
        _fail("did.csv clusters below minimum")
    if not cov_path.is_file():
        _fail("no coverage.csv")
    with cov_path.open(encoding="utf-8-sig", newline="") as f:
        cov_rows = list(csv.DictReader(f))
    if not cov_rows:
        _fail("coverage.csv is empty")
    for r in cov_rows:
        _row_identity_errors(r, expect, "coverage.csv")
    p0 = [r for r in cov_rows if (r.get("tier") or "") == "P0"]
    if not p0 or not all((r.get("complete") or "") == "1" for r in p0):
        _fail("coverage.csv P0 is not complete")
    return {
        "did_excludes_zero": "是",
        "did_positive": "是",
        "treat_clusters": str(tc),
        "holdout_clusters": str(hc),
        "coverage_ok": "是",
    }


def _check_verdict(stage: str, sop: str, fields: dict, incoming: dict) -> None:
    v = incoming.get("verdict_4")
    if not v:
        return
    if v not in VERDICT_OK.get(sop, ()):
        _fail(f"verdict_4 {v} not allowed for {sop}")
    if stage == "03" and sop == "冲刺" and v in {"受控前后描述", "确认性 L1"}:
        _fail("sprint verdict_4 is written at 05 after retest")
    if v == "确认性 L1":
        if sop != "冲刺" or stage != "05":
            _fail("confirmatory L1 only after sprint retest at 05")
        if fields.get("causal_claim") != "did_isolated":
            _fail("confirmatory L1 requires causal_claim=did_isolated")
        if not _is_yes(fields.get("did_excludes_zero")) or not _is_yes(fields.get("did_positive")):
            _fail("confirmatory L1 requires positive DiD excluding 0")
        try:
            tc = int(str(fields.get("treat_clusters") or "0"))
            hc = int(str(fields.get("holdout_clusters") or "0"))
        except ValueError:
            tc, hc = 0, 0
        if tc < MIN_DID_CLUSTERS or hc < MIN_DID_CLUSTERS:
            _fail("confirmatory L1 requires at least 2 treat and 2 holdout clusters")
        if not _is_yes(fields.get("coverage_ok")):
            _fail("confirmatory L1 requires coverage_ok")


def apply_fields(state: dict, payload: dict, actor: str = "agent", cases_root: Path | None = None) -> dict:
    import review as _rv

    if actor == "human":
        _fail("human does not apply fields; use decide()")
    _rv.teaching.ensure_process(state)
    if state.get("activity") in _rv.BLOCK_APPLY:
        _fail("review blocks apply")
    if _rv.review_engaged(state):
        _rv.validate_current_review_target(state, cases_root)
        if not _rv.stage_allows_apply(state):
            _fail("review not passed")
    if state["waiting"] != "agent":
        _fail(f"waiting on {state['waiting']}, not agent apply")
    stage = state["stage"]
    writers = load_writers()
    incoming = dict(payload.get("fields") or {})
    if stage == "01" and "sop_stage" in incoming:
        incoming["sop_stage_intent"] = incoming.pop("sop_stage")
    sop_now = state["fields"].get("sop_stage") or incoming.get("sop_stage") or state["fields"].get("sop_stage_intent") or ""
    for key in incoming:
        owner = _owner_for(key, stage, sop_now)
        if owner is None and key not in writers:
            _fail(f"unknown field {key}")
        if owner is None:
            owner = writers.get(key)
        prev = state["fields"].get(key)
        if owner != stage:
            if prev is None or str(incoming[key]) != str(prev):
                _fail(f"{key} owned by {owner}, current {stage}")
        text = str(incoming[key])
        for bad in BANNED_CLAIMS:
            if bad in text:
                _fail(f"banned claim in {key}: {bad}")
    if stage == "02" and "sop_stage" in incoming:
        intent = state["fields"].get("sop_stage_intent") or incoming.get("sop_stage")
        locked = incoming["sop_stage"]
        if locked not in VERDICT_OK:
            _fail(f"bad sop_stage {locked}")
        if intent and locked != intent and locked not in NARROW.get(intent, ()):
            _fail(f"cannot widen sop_stage {intent} -> {locked}")
    if stage == "07":
        sop = state["fields"].get("sop_stage")
        scope = str(incoming.get("budget_scope", state["fields"].get("budget_scope", "")))
        if sop == "诊断" and any(tok in scope for tok in DIAG_BUDGET_BAN):
            _fail("diagnosis budget cannot include intervention")
        quote = incoming.get("quote_excludes_l1", state["fields"].get("quote_excludes_l1"))
        if quote is not None and not _is_yes(quote):
            _fail("quote must exclude L1")
    if stage == "08":
        bound = str(incoming.get("comms_bound", state["fields"].get("comms_bound", "")))
        if bound and "四选一" not in bound and "不得宽于" not in bound:
            _fail("comms_bound must stay within verdict_4")
    if stage == "04":
        windows = set(payload.get("windows") or [])
        sop = state["fields"].get("sop_stage")
        allowed = STAGE_WINDOWS.get(sop or "", frozenset())
        extra = windows - allowed
        if extra:
            _fail(f"windows not allowed for {sop}: {sorted(extra)}")
    if stage == "05":
        sop = state["fields"].get("sop_stage")
        klass = incoming.get("intervention_class", state["fields"].get("intervention_class", ""))
        if sop == "诊断" and klass not in {"", "无"}:
            _fail("diagnosis cannot set intervention_class")
        if sop == "诊断":
            incoming["intervention_class"] = "无"
        for key in L1_DERIVED:
            incoming.pop(key, None)
        if incoming.get("verdict_4") == "确认性 L1":
            incoming.update(derive_l1_from_files(state["case_id"], _merged_fields(state, incoming, payload), cases_root))
    if stage == "03":
        fid = incoming.get("freeze_id", state["fields"].get("freeze_id", ""))
        fd = resolve_freeze_dir(str(fid), state["case_id"], cases_root)
        if not fd:
            _fail(f"freeze_id not found: {fid}")
        merged = _merged_fields(state, incoming, payload)
        mismatch = freeze_contract_errors(fd, merged)
        if mismatch:
            _fail("freeze does not match case contract: " + ",".join(mismatch))
        isolate_measure_case(state["case_id"], str(fid), cases_root)
        incoming["measure_isolated"] = "是"
        incoming["config_checksum"] = freeze_files_checksum(fd)
        if not incoming["config_checksum"]:
            _fail("freeze missing checksum")
        sop = sop_now or state["fields"].get("sop_stage")
        bv = incoming.get("baseline_verdict_4")
        if bv and bv not in {"描述基线", "不能下结论"}:
            _fail("baseline_verdict_4 must be 描述基线 or 不能下结论")
        _check_verdict(stage, sop, _merged_fields(state, incoming, payload), incoming)
        if sop != "冲刺" and "verdict_4" not in incoming and bv:
            incoming["verdict_4"] = bv
    if stage == "06":
        sop = state["fields"].get("sop_stage")
        v = incoming.get("verdict_4")
        prior = state["fields"].get("verdict_4")
        if v and prior and v != prior:
            _fail("verdict_4 must match locked value")
        _check_verdict(stage, sop or "", _merged_fields(state, incoming, payload), incoming)
    if stage == "05":
        sop = state["fields"].get("sop_stage")
        _check_verdict(stage, sop or "", _merged_fields(state, incoming, payload), incoming)
    if stage == "09":
        assets = incoming.get("close_assets_ok")
        if assets is not None and not _is_yes(assets):
            _fail("assets not deposited")
        reopen = incoming.get("close_no_reopen_l1")
        if reopen is not None and not _is_yes(reopen):
            _fail("cannot reopen L1 at close")
        v = incoming.get("verdict_4")
        prior = state["fields"].get("verdict_4")
        if v and prior and v != prior:
            _fail("verdict_4 must match locked value")
    miss = missing_required(state, incoming, payload, cases_root=cases_root)
    if miss:
        _fail("missing required: " + ",".join(miss))
    state["fields"].update(incoming)
    if "windows" in payload:
        state["fields"]["windows"] = list(payload["windows"])
    state["waiting"] = "human"
    state["activity"] = "human_gate"
    if stage == "05" and state["fields"].get("sop_stage") == "诊断":
        state["gates"]["G5"] = {"verdict": "N/A", "actor": "system", "at": now()}
        state["waiting"] = "human"
        state["activity"] = "human_gate"
    state["log"].append({"at": now(), "op": "apply", "stage": stage, "keys": sorted(incoming)})
    return state


def _clear_from(state: dict, target: str, cases_root: Path | None = None) -> None:
    writers = load_writers()
    later = set(STAGES[STAGES.index(target) :])
    sop = state["fields"].get("sop_stage") or ""
    drop = []
    for key in list(state["fields"]):
        owner = _owner_for(key, target, sop) or writers.get(key)
        if owner in later:
            drop.append(key)
    for key in drop:
        state["fields"].pop(key, None)
    if target == "04" or "04" in later:
        state["fields"].pop("windows", None)
    for st in later:
        state["gates"].pop(GATE_AFTER[st], None)
    state["stage"] = target
    state["waiting"] = "agent"
    import review as _rv

    _rv.reset_stage_review(state)
    import files as _files

    later = list(STAGES[STAGES.index(target) :])
    _files.invalidate_from(state["case_id"], later, cases_root)


def decide(
    state: dict,
    gate: str,
    verdict: str,
    actor: str = "human",
    cases_root: Path | None = None,
    rewind_to: str | None = None,
) -> dict:
    if actor != "human" and verdict == "APPROVE":
        _fail("only human may APPROVE")
    need = GATE_AFTER[state["stage"]]
    if gate != need:
        _fail(f"current gate is {need}, not {gate}")
    if state["waiting"] != "human" and not (
        state["stage"] == "05" and state["gates"].get("G5", {}).get("verdict") == "N/A"
    ):
        if state["waiting"] != "human":
            _fail("nothing for human to decide")
    if verdict not in {"APPROVE", "REJECT", "CHANGE"}:
        _fail(f"bad verdict {verdict}")
    if verdict == "APPROVE":
        import review as _rv

        _rv.teaching.ensure_process(state)
        if _rv.review_engaged(state):
            _rv.validate_current_review_target(state, cases_root)
            if not _rv.stage_allows_apply(state):
                _fail("review not passed")
        miss = missing_required(state, cases_root=cases_root)
        if miss:
            _fail("missing required: " + ",".join(miss))
    state["gates"][gate] = {"verdict": verdict, "actor": actor, "at": now()}
    state["log"].append({"at": now(), "op": "decide", "gate": gate, "verdict": verdict})
    if verdict == "APPROVE":
        import files as _files
        import review as _rv

        _files.promote_stage_outputs(state, cases_root)
        idx = STAGES.index(state["stage"])
        if idx + 1 < len(STAGES):
            state["stage"] = STAGES[idx + 1]
            state["waiting"] = "agent"
            _rv.reset_stage_review(state)
        else:
            state["waiting"] = "done"
            state["activity"] = "done"
    elif verdict == "REJECT":
        state["waiting"] = "agent"
        state["activity"] = "agent_draft" if (state.get("review") or {}).get("current_result") in {"PASS", "OVERRIDE_SOFT"} else "material_pending"
    else:
        target = rewind_to or state["stage"]
        if target not in STAGES:
            _fail(f"bad rewind_to {target}")
        if STAGES.index(target) > STAGES.index(state["stage"]):
            _fail("cannot CHANGE forward")
        _clear_from(state, target, cases_root)
    return state


def status(state: dict) -> dict:
    nxt = next_action(state)
    nxt["fields"] = dict(state["fields"])
    nxt["gates"] = dict(state["gates"])
    return nxt
