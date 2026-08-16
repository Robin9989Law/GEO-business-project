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
# 关键门：必须双角色审批（详见 报告 P1 §1）
GATE_DUAL_APPROVERS = frozenset({"G1", "G3", "G4", "G8"})
# 关键门需要的角色集合（两个角色必须不同）
GATE_REQUIRED_ROLES = {
    "G1": ("负责人", "GEO/验收专业复核"),
    "G3": ("负责人", "测量复核"),
    "G4": ("负责人/客户成功", "测量复核"),
    "G8": ("负责人", "文件/资产复核"),
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
    "诊断": frozenset({"day0", "noise", "baseline"}),
    "冲刺": frozenset({"day0", "noise", "baseline", "intervention", "wait", "retest"}),
    "续约": frozenset({"day0", "weekly", "calib"}),
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
PRIMARY_GOAL_TEXT = "在无品牌发现问上提高被正确提及的概率"
CAUSAL_CLAIM_OK = frozenset({"descriptive_until_isolation", "did_isolated", "pre_registered_did"})
SUCCESS_RULE_OK = {
    "success_rule_diagnosis": frozenset({"描述基线", "不能下结论"}),
    "success_rule_sprint": frozenset({"受控前后描述", "确认性 L1", "不能下结论"}),
    "success_rule_retain": frozenset({"不能下结论"}),
}
BUDGET_SCOPE_OK = {
    "诊断": frozenset({"冻结", "噪声", "基线", "抽检", "收尾"}),
    "冲刺": frozenset({"冻结", "噪声", "基线", "抽检", "收尾", "干预", "一类证据", "复测", "等待"}),
    "续约": frozenset({"weekly", "calib", "监测", "收尾"}),
}
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
    "08": ("stakeholder_decision", "comms_cadence", "comms_bound", "comms_api_not_primary"),
    "03": ("freeze_id", "data_grade", "baseline_verdict_4", "measure_isolated"),
    "04": ("plan_hours",),
    "05": ("intervention_class",),
    "06": ("verdict_4", "delivery_manifest_checksum", "freeze_match", "delivery_accepted"),
    "09": ("close_assets_ok", "close_no_reopen_l1", "close_manifest_ok", "close_board_empty", "close_archive_ok"),
}
MIN_DID_CLUSTERS = 2
FREEZE_ROOT = ROOT / "流程" / "03 测量" / "配置" / "冻结"
MEASURE_CASES = ROOT / "流程" / "03 测量" / "案件"


def load_writers(path: Path = FIELDS_CSV) -> dict[str, frozenset]:
    out: dict[str, frozenset] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            field = (row.get("field") or "").strip()
            stage = (row.get("writer_stage") or "").strip()
            if field and stage:
                out[field] = frozenset(s for s in stage.split("|") if s)
    out.setdefault("sop_stage_intent", frozenset({"01"}))
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
        "writable_fields": [f for f, s in load_writers().items() if stage in s],
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


def _owner_for(key: str, stage: str, sop: str) -> frozenset | None:
    writers = load_writers()
    if key == "verdict_4" and sop == "冲刺":
        return frozenset({"05"})
    if key == "verdict_4":
        return frozenset({"03"})
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
    if stage == "04":
        try:
            plan = float(str(fields.get("plan_hours") or "").strip())
            budget = float(str(fields.get("budget_hours") or "").strip())
            if plan <= 0 or plan > budget:
                miss.append("plan_hours")
        except ValueError:
            miss.append("plan_hours")
    if stage == "02":
        if _norm_ids(fields.get("treat_need_ids")) & _norm_ids(fields.get("holdout_need_ids")):
            miss.append("need_overlap")
    if stage == "05" and sop == "冲刺":
        for key in ("intervention_need_ids", "holdout_untouched", "intervention_completed_on", "wait_days"):
            if not str(fields.get(key) or "").strip():
                miss.append(key)
        if fields.get("holdout_untouched") and not _is_yes(fields.get("holdout_untouched")):
            miss.append("holdout_untouched")
        extra = _norm_ids(fields.get("intervention_need_ids")) - _norm_ids(fields.get("treat_need_ids"))
        if extra:
            miss.append("intervention_need_ids")
        try:
            if float(str(fields.get("wait_days") or "").strip()) < 0:
                miss.append("wait_days")
        except ValueError:
            miss.append("wait_days")
    if stage == "06":
        if fields.get("freeze_match") and not _is_yes(fields.get("freeze_match")):
            miss.append("freeze_match")
        if fields.get("delivery_accepted") and not _is_yes(fields.get("delivery_accepted")):
            miss.append("delivery_accepted")
    if stage == "08" and fields.get("comms_api_not_primary") is not None and not _is_yes(fields.get("comms_api_not_primary")):
        miss.append("comms_api_not_primary")
    if stage == "09":
        for key in ("close_manifest_ok", "close_board_empty", "close_archive_ok"):
            if fields.get(key) is not None and not _is_yes(fields.get(key)):
                miss.append(key)
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


SHARED_DELIVERY = ROOT / "流程" / "03 测量" / "出数"
DELIVERY_REQUIRED_FILES = (
    "evidence_manifest.json",
    "metrics_daily.csv",
    "coverage.csv",
)
DELIVERY_OPTIONAL_FILES = ("did.csv",)
REPORT_SUFFIXES = {".md", ".pdf"}
REPORT_SKIP_NAMES = frozenset({"README.md", "报告模板.md", "INVALIDATED.txt"})
EXPECTED_FORMAL_DOCS = {
    "01": ("01_商机卡",),
    "02": ("02_章程",),
    "07": ("07_预算",),
    "08": ("08_沟通矩阵",),
    "04": ("04_进度",),
    "05": ("05_周报",),
    "06": ("06_验收单",),
}
CLOSE_DRAFTS = ("09_结项报告.md", "09_经验教训.md", "09_资产移交.md")
IDENTITY_KEYS = ("case_id", "project_id", "freeze_id", "config_checksum")


def _is_shared_delivery(path: Path) -> bool:
    try:
        path.resolve().relative_to(SHARED_DELIVERY.resolve())
        return True
    except (ValueError, OSError):
        return False


def delivery_report_files(out_dir: Path) -> list[Path]:
    found: list[Path] = []
    if not Path(out_dir).is_dir():
        return found
    skip = set(DELIVERY_REQUIRED_FILES) | set(DELIVERY_OPTIONAL_FILES) | set(REPORT_SKIP_NAMES)
    for p in sorted(Path(out_dir).iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.name in skip:
            continue
        if p.suffix.lower() in REPORT_SUFFIXES:
            found.append(p)
    return found


def resolve_delivery_dir(case_id: str, cases_root: Path | None = None) -> Path | None:
    for d in _measure_out_dirs(case_id, cases_root):
        if not d.is_dir():
            continue
        if _is_shared_delivery(d):
            continue
        if all((d / name).is_file() for name in DELIVERY_REQUIRED_FILES):
            return d
    return None


def _delivery_hash_paths(out_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for name in DELIVERY_REQUIRED_FILES:
        p = Path(out_dir) / name
        if p.is_file():
            paths.append(p)
    for name in DELIVERY_OPTIONAL_FILES:
        p = Path(out_dir) / name
        if p.is_file():
            paths.append(p)
    paths.extend(delivery_report_files(out_dir))
    return paths


def delivery_files_checksum(out_dir: Path) -> str:
    if not all((Path(out_dir) / name).is_file() for name in DELIVERY_REQUIRED_FILES):
        return ""
    if not delivery_report_files(out_dir):
        return ""
    h = hashlib.sha256()
    for p in _delivery_hash_paths(out_dir):
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def expected_formal_doc_ids() -> tuple[str, ...]:
    """P0-3 同步：与 `合同/阶段交付物注册.md` / `files.STAGE_DELIVERABLES` 一致（09 除外）。

    只列 required=True 的 doc_id。required=False 的（如 `05_干预轮次卡` 仅冲刺）按 sop_stage 动态决定。
    """
    import files as _files
    ids: list[str] = []
    for stage in STAGES:
        if stage == "09":
            break
        for doc_id, info in _files.STAGE_DELIVERABLES.get(stage, {}).items():
            if info.get("required"):
                ids.append(doc_id)
    return tuple(ids)


def _resolve_vault_file(vault: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_file():
        return p
    cand = vault / rel_or_abs
    if cand.is_file():
        return cand
    try:
        cand = ROOT / rel_or_abs
        if cand.is_file():
            return cand
    except OSError:
        pass
    return p


def formal_docs_checksum_errors(
    case_id: str,
    cases_root: Path | None = None,
    state: dict | None = None,
) -> list[str]:
    import files as _files

    vault = _files.vault_path(case_id, cases_root)
    current_dir = vault / "正式" / "现行"
    docs = _files._docs(vault)
    current = [d for d in docs if d.get("status") == "现行"]
    if not current:
        return ["empty_manifest"]
    errs: list[str] = []
    by_id = {d.get("doc_id") or "": d for d in current}
    for doc_id in expected_formal_doc_ids():
        if doc_id not in by_id:
            errs.append(f"missing:{doc_id}")
    gates = (state or {}).get("gates") or {}
    registered_names: set[str] = set()
    for doc in current:
        doc_id = doc.get("doc_id") or ""
        suffix = Path(doc.get("path") or ".md").suffix or ".md"
        current_p = current_dir / f"{doc_id}{suffix}"
        if not current_p.is_file():
            hits = list(current_dir.glob(doc_id + ".*")) if doc_id else []
            current_p = hits[0] if hits else current_p
        if current_p.is_file():
            registered_names.add(current_p.name)
        if not current_p.is_file() or _files._sha256(current_p) != (doc.get("checksum") or ""):
            errs.append(doc_id or "doc")
        gate = (doc.get("gate") or "").strip()
        if gate:
            verdict = (gates.get(gate) or {}).get("verdict")
            if verdict not in {"APPROVE", "N/A"}:
                errs.append(f"gate:{doc_id}:{gate}")
    if current_dir.is_dir():
        for p in current_dir.iterdir():
            if p.is_file() and not p.name.startswith(".") and p.name not in registered_names:
                errs.append(f"unregistered:{p.name}")
    for doc in docs:
        if doc.get("status") not in {"历史", "现行"}:
            continue
        stored = _resolve_vault_file(vault, doc.get("path") or "")
        if not stored.is_file() or _files._sha256(stored) != (doc.get("checksum") or ""):
            errs.append(f"version:{doc.get('doc_id') or 'doc'}:r{doc.get('rev') or '?'}")
    return errs


def case_out_dir(case_id: str, cases_root: Path | None) -> Path:
    return (cases_root or DEFAULT_CASES) / case_id / "out"


def closeout_draft_paths(case_id: str, cases_root: Path | None) -> list[Path]:
    base = case_out_dir(case_id, cases_root)
    found: list[Path] = []
    for name in CLOSE_DRAFTS:
        for cand in (base / name, base / "09" / name):
            if cand.is_file():
                found.append(cand)
                break
    return found


def closeout_draft_errors(case_id: str, fields: dict, cases_root: Path | None) -> list[str]:
    import files as _files

    base = case_out_dir(case_id, cases_root)
    errs: list[str] = []
    verdict = str(fields.get("verdict_4") or "").strip()
    for name in CLOSE_DRAFTS:
        p = base / name
        if not p.is_file():
            p = base / "09" / name
        if not p.is_file():
            errs.append(f"missing:{name}")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            errs.append(f"empty:{name}")
            continue
        hits = _files.find_banned(p)
        if hits:
            errs.append(f"banned:{name}:{hits[0]}")
        if verdict != "确认性 L1" and "实际交付：确认性 L1" in text.replace(" ", ""):
            errs.append(f"reopen_l1:{name}")
        if "close_no_reopen_l1" in text and "close_no_reopen_l1：否" in text.replace(" ", ""):
            errs.append(f"reopen_l1:{name}")
    return errs


def _deposit_csv_paths(case_id: str, cases_root: Path | None) -> list[Path]:
    paths = []
    if cases_root is not None:
        paths.append(Path(cases_root) / case_id / "measure" / "资产库" / "登记" / "deposits.csv")
    paths.append(MEASURE_CASES / case_id / "资产库" / "登记" / "deposits.csv")
    paths.append(ROOT / "流程" / "03 测量" / "资产库" / "登记" / "deposits.csv")
    return paths


def _plays_csv_paths(case_id: str, cases_root: Path | None) -> list[Path]:
    paths = []
    if cases_root is not None:
        paths.append(Path(cases_root) / case_id / "measure" / "资产库" / "干预复盘" / "plays.csv")
    paths.append(MEASURE_CASES / case_id / "资产库" / "干预复盘" / "plays.csv")
    paths.append(ROOT / "流程" / "03 测量" / "资产库" / "干预复盘" / "plays.csv")
    return paths


def deposit_recorded(case_id: str, fields: dict, cases_root: Path | None) -> bool:
    tools = str(ROOT / "流程" / "03 测量" / "工具")
    import sys

    if tools not in sys.path:
        sys.path.insert(0, tools)
    from asset_deposit import anon_project

    want = anon_project(str(fields.get("project_id") or "").strip())
    for path in _deposit_csv_paths(case_id, cases_root):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                anon = str(row.get("project_anon") or "").strip()
                cid = str(row.get("case_id") or "").strip()
                status = str(row.get("status") or "").strip()
                if cid == case_id and status:
                    return True
                if want and anon == want and status:
                    return True
    return False


def _surfaces_from_freeze(fd: Path | None) -> tuple[set[str], set[str]]:
    banned: set[str] = set()
    owned: set[str] = set()
    if fd is None or not fd.is_dir():
        return banned, owned
    aliases = fd / "aliases.csv"
    if aliases.is_file():
        for row in _read_csv_rows(aliases):
            if (row.get("type") or "") == "self" and (row.get("surface") or "").strip():
                banned.add(row["surface"].strip())
    owned_p = fd / "owned_sources.csv"
    if owned_p.is_file():
        from urllib.parse import urlparse

        for row in _read_csv_rows(owned_p):
            pat = (row.get("pattern") or "").lower()
            if not pat:
                continue
            if "://" in pat:
                host = urlparse(pat).netloc.lower().removeprefix("www.")
            else:
                host = pat.replace("www.", "")
            if host:
                owned.add(host)
    return banned, owned


def close_leaks(case_id: str, fields: dict, cases_root: Path | None) -> list[str]:
    tools = str(ROOT / "流程" / "03 测量" / "工具")
    import sys

    if tools not in sys.path:
        sys.path.insert(0, tools)
    from asset_deposit import leak_scan

    fid = str(fields.get("freeze_id") or "").strip()
    fd = resolve_freeze_dir(fid, case_id, cases_root) if fid else None
    banned, owned = _surfaces_from_freeze(fd)
    blob = ""
    for p in closeout_draft_paths(case_id, cases_root):
        blob += p.read_text(encoding="utf-8", errors="replace")
    for path in _deposit_csv_paths(case_id, cases_root):
        if path.is_file() and (cases_root is None or _is_under(path, Path(cases_root))):
            blob += path.read_text(encoding="utf-8", errors="replace")
    return leak_scan(blob, banned, owned)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def plays_recorded(case_id: str, cases_root: Path | None) -> bool:
    for path in _plays_csv_paths(case_id, cases_root):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f) if any(str(v or "").strip() for v in r.values())]
        if rows:
            return True
    return False


def archive_errors(case_id: str, fields: dict, cases_root: Path | None) -> list[str]:
    import files as _files

    errs: list[str] = []
    board = _files.board(case_id, cases_root)
    if board.get("locks"):
        errs.append("locks")
    if not deposit_recorded(case_id, fields, cases_root):
        errs.append("deposits")
    handover = [p for p in closeout_draft_paths(case_id, cases_root) if p.name == "09_资产移交.md"]
    if not handover:
        errs.append("handover")
    leaks = close_leaks(case_id, fields, cases_root)
    if leaks:
        errs.append("leak")
    if str(fields.get("sop_stage") or "") == "冲刺" and not plays_recorded(case_id, cases_root):
        errs.append("plays")
    return errs


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _csv_identity_errors(path: Path, expect: dict, label: str) -> list[str]:
    if not path.is_file():
        return [f"{label}:missing"]
    rows = _read_csv_rows(path)
    if not rows:
        return [f"{label}:empty"]
    header = set(rows[0].keys())
    miss_cols = [k for k in IDENTITY_KEYS if k not in header]
    if miss_cols:
        return [f"{label}:no_identity"]
    errs = []
    for i, row in enumerate(rows):
        for key in IDENTITY_KEYS:
            got = str(row.get(key) or "").strip()
            want = str(expect.get(key) or "").strip()
            if not got:
                errs.append(f"{label}:missing_{key}")
            elif got != want:
                errs.append(f"{label}:mismatch_{key}")
        if errs:
            return errs
        if i > 200:
            break
    return errs


def _manifest_file_digest(man: dict, name: str, path: Path) -> list[str]:
    files = man.get("files") or {}
    if name not in files:
        return [f"manifest:missing_{name}"]
    if not path.is_file() or files.get(name) != _file_digest(path):
        return [f"manifest:checksum_{name}"]
    return []


def delivery_identity_errors(out_dir: Path, expect: dict) -> list[str]:
    man_p = Path(out_dir) / "evidence_manifest.json"
    daily_p = Path(out_dir) / "metrics_daily.csv"
    cov_p = Path(out_dir) / "coverage.csv"
    did_p = Path(out_dir) / "did.csv"
    errs: list[str] = []
    if not man_p.is_file():
        return ["evidence_manifest"]
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["evidence_manifest"]
    for key in IDENTITY_KEYS:
        got = str(man.get(key) or "").strip()
        want = str(expect.get(key) or "").strip()
        if not got or got != want:
            errs.append(f"manifest:{key}")
    errs.extend(_manifest_file_digest(man, "metrics_daily.csv", daily_p))
    errs.extend(_manifest_file_digest(man, "coverage.csv", cov_p))
    errs.extend(_csv_identity_errors(daily_p, expect, "metrics_daily.csv"))
    errs.extend(_csv_identity_errors(cov_p, expect, "coverage.csv"))
    if did_p.is_file():
        errs.extend(_csv_identity_errors(did_p, expect, "did.csv"))
        files = man.get("files") or {}
        if "did.csv" in files and files.get("did.csv") != _file_digest(did_p):
            errs.append("manifest:checksum_did.csv")
    return errs


def _enforce_delivery(state: dict, incoming: dict, cases_root: Path | None) -> None:
    out = resolve_delivery_dir(state.get("case_id") or "", cases_root)
    if out is None:
        _fail("no case delivery files under 案件/{本案}/出数")
    if not delivery_report_files(out):
        _fail("no customer delivery report")
    computed = delivery_files_checksum(out)
    if not computed:
        _fail("no case delivery files under 案件/{本案}/出数")
    stated = incoming.get("delivery_manifest_checksum", state["fields"].get("delivery_manifest_checksum"))
    if stated and str(stated).strip() != computed:
        _fail("delivery_manifest_checksum mismatch")
    incoming["delivery_manifest_checksum"] = computed
    fid = str(state["fields"].get("freeze_id") or incoming.get("freeze_id") or "").strip()
    fd = resolve_freeze_dir(fid, state.get("case_id") or "", cases_root)
    if fd is None:
        _fail("delivery freeze_id must match locked freeze")
    merged = _merged_fields(state, incoming, {})
    mismatch = freeze_contract_errors(fd, merged)
    if mismatch:
        _fail("delivery freeze_id must match locked freeze")
    expect = _evidence_identity(state.get("case_id") or "", merged)
    ident_errs = delivery_identity_errors(out, expect)
    if ident_errs:
        _fail("delivery identity does not match freeze: " + ",".join(ident_errs[:6]))
    incoming["freeze_match"] = "是"


def _enforce_close(state: dict, incoming: dict, cases_root: Path | None) -> None:
    import files as _files

    case_id = state.get("case_id") or ""
    merged = _merged_fields(state, incoming, {})
    board = _files.board(case_id, cases_root)
    if board.get("pending"):
        _fail("transfer board still has pending items")
    incoming["close_board_empty"] = "是"
    draft_errs = closeout_draft_errors(case_id, merged, cases_root)
    if draft_errs:
        _fail("closeout drafts missing or invalid")
    arch_errs = archive_errors(case_id, merged, cases_root)
    if arch_errs:
        _fail("archive checklist incomplete")
    incoming["close_archive_ok"] = "是"
    doc_errs = formal_docs_checksum_errors(case_id, cases_root, state)
    if doc_errs:
        _fail("formal manifest does not match gates")
    incoming["close_manifest_ok"] = "是"
    locked = str(state["fields"].get("delivery_manifest_checksum") or "").strip()
    out = resolve_delivery_dir(case_id, cases_root)
    computed = delivery_files_checksum(out) if out else ""
    if not locked or not computed or locked != computed:
        _fail("delivery checksum changed since G4")


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
            owner = writers.get(key) or frozenset()
        prev = state["fields"].get(key)
        if stage not in owner:
            if prev is None or str(incoming[key]) != str(prev):
                _fail(f"{key} owned by {sorted(owner)}, current {stage}")
        text = str(incoming[key])
        for bad in BANNED_CLAIMS:
            if bad in text:
                _fail(f"banned claim in {key}: {bad}")
    if stage == "02":
        treat = _norm_ids(incoming.get("treat_need_ids", state["fields"].get("treat_need_ids")))
        hold = _norm_ids(incoming.get("holdout_need_ids", state["fields"].get("holdout_need_ids")))
        if treat and hold and treat & hold:
            _fail("treat and holdout need ids must be disjoint")
    if stage == "02" and "sop_stage" in incoming:
        intent = state["fields"].get("sop_stage_intent") or incoming.get("sop_stage")
        locked = incoming["sop_stage"]
        if locked not in VERDICT_OK:
            _fail(f"bad sop_stage {locked}")
        if intent and locked != intent and locked not in NARROW.get(intent, ()):
            _fail(f"cannot widen sop_stage {intent} -> {locked}")
    if stage == "02":
        goal = incoming.get("primary_goal", state["fields"].get("primary_goal"))
        if goal is not None and str(goal).strip() != PRIMARY_GOAL_TEXT:
            _fail(f"primary_goal must be '{PRIMARY_GOAL_TEXT}'")
        ep = incoming.get("primary_endpoint", state["fields"].get("primary_endpoint"))
        if ep is not None and str(ep).strip() != "p_mention":
            _fail("primary_endpoint must be p_mention")
        cc = incoming.get("causal_claim", state["fields"].get("causal_claim"))
        if cc is not None and str(cc).strip() not in CAUSAL_CLAIM_OK:
            _fail(f"causal_claim must be one of {sorted(CAUSAL_CLAIM_OK)}")
        cd = incoming.get("control_design", state["fields"].get("control_design"))
        if cd is not None:
            cd_s = str(cd).strip()
            if cd_s != "监测组":
                _fail("control_design must be 监测组")
            if "反事实" in cd_s:
                _fail("control_design must not be called 反事实")
        sr_d = incoming.get("success_rule_diagnosis", state["fields"].get("success_rule_diagnosis"))
        if sr_d is not None and str(sr_d).strip() not in SUCCESS_RULE_OK["success_rule_diagnosis"]:
            _fail(f"success_rule_diagnosis must be in {sorted(SUCCESS_RULE_OK['success_rule_diagnosis'])}")
        sr_s = incoming.get("success_rule_sprint", state["fields"].get("success_rule_sprint"))
        if sr_s is not None and str(sr_s).strip() not in SUCCESS_RULE_OK["success_rule_sprint"]:
            _fail(f"success_rule_sprint must be in {sorted(SUCCESS_RULE_OK['success_rule_sprint'])}")
        sr_r = incoming.get("success_rule_retain", state["fields"].get("success_rule_retain"))
        if sr_r is not None and str(sr_r).strip() not in SUCCESS_RULE_OK["success_rule_retain"]:
            _fail(f"success_rule_retain must be in {sorted(SUCCESS_RULE_OK['success_rule_retain'])}")
        plats = incoming.get("platforms_required", state["fields"].get("platforms_required"))
        if plats is not None:
            pset = _norm_ids(plats)
            if not pset:
                _fail("platforms_required must be a non-empty set")
    if stage == "07":
        sop = state["fields"].get("sop_stage")
        scope = str(incoming.get("budget_scope", state["fields"].get("budget_scope", "")))
        if sop == "诊断" and any(tok in scope for tok in DIAG_BUDGET_BAN):
            _fail("diagnosis budget cannot include intervention")
        if sop in BUDGET_SCOPE_OK and scope:
            allowed = BUDGET_SCOPE_OK[sop]
            for tok in scope.replace("，", ",").replace("+", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                if tok not in allowed:
                    _fail(f"budget_scope token '{tok}' not in {sop} allowed set {sorted(allowed)}")
        quote = incoming.get("quote_excludes_l1", state["fields"].get("quote_excludes_l1"))
        if quote is not None and not _is_yes(quote):
            _fail("quote must exclude L1")
    if stage == "08":
        bound = str(incoming.get("comms_bound", state["fields"].get("comms_bound", "")))
        if bound and "四选一" not in bound and "不得宽于" not in bound:
            _fail("comms_bound must stay within verdict_4")
        api_flag = incoming.get("comms_api_not_primary", state["fields"].get("comms_api_not_primary"))
        if api_flag is not None and not _is_yes(api_flag):
            _fail("decision maker cannot use API as primary table")
    if stage == "04":
        windows = set(payload.get("windows") or [])
        sop = state["fields"].get("sop_stage")
        allowed = STAGE_WINDOWS.get(sop or "", frozenset())
        extra = windows - allowed
        if extra:
            _fail(f"windows not allowed for {sop}: {sorted(extra)}")
        plan_raw = incoming.get("plan_hours", state["fields"].get("plan_hours"))
        budget_raw = state["fields"].get("budget_hours")
        if plan_raw is not None:
            try:
                plan = float(str(plan_raw).strip())
                budget = float(str(budget_raw or "").strip())
            except ValueError:
                _fail("plan_hours must be a number")
            else:
                if plan <= 0:
                    _fail("plan_hours must be > 0")
                if plan > budget:
                    _fail("plan_hours cannot exceed budget_hours")
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
        if sop == "冲刺":
            needs = _norm_ids(incoming.get("intervention_need_ids", state["fields"].get("intervention_need_ids")))
            treat = _norm_ids(state["fields"].get("treat_need_ids"))
            if needs - treat:
                _fail("intervention needs must belong to treat_need_ids")
            hold = incoming.get("holdout_untouched", state["fields"].get("holdout_untouched"))
            if hold is not None and not _is_yes(hold):
                _fail("holdout group must stay untouched")
            if incoming.get("wait_days", state["fields"].get("wait_days")) is not None:
                try:
                    if float(str(incoming.get("wait_days", state["fields"].get("wait_days"))).strip()) < 0:
                        _fail("wait_days must be >= 0")
                except ValueError:
                    _fail("wait_days must be a number")
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
        if incoming.get("delivery_accepted") is not None and not _is_yes(incoming.get("delivery_accepted")):
            _fail("delivery not accepted; cannot proceed to close")
        _enforce_delivery(state, incoming, cases_root)
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
        if incoming.get("verdict_4") == "确认性 L1" and prior != "确认性 L1":
            _fail("cannot reopen L1 at close")
        if v and prior and v != prior:
            _fail("verdict_4 must match locked value")
        _enforce_close(state, incoming, cases_root)
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
        owner = _owner_for(key, target, sop) or writers.get(key) or frozenset()
        if owner & later:
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
    member: str = "",
    role: str = "",
    decision_reason: str = "",
    required_outputs: list | None = None,
    hard_check_results: dict | None = None,
    quality_review_id: str = "",
    evidence_checksum: str = "",
    change_payload: dict | None = None,
) -> dict:
    """P1: 完整 Gate Packet + 关键门双签 + CHANGE 影响分析。

    参数:
      member: 签字人代号（必填；关键门必须两次不同 member）
      role: 签字人角色（必填；必须在 GATE_REQUIRED_ROLES[gate] 中）
      decision_reason: 决策原因（建议填；空时 log 警告）
      required_outputs: 必填的产出 doc_id 列表（用于审计）
      hard_check_results: 硬规则检查结果（dict）
      quality_review_id: 质检记录 ID（由 review 模块填）
      evidence_checksum: 证据/出数校验和
      change_payload: 当 verdict="CHANGE" 时的影响分析 dict：
        - reason: 变更原因
        - affected_fields: 受影响字段
        - affected_docs: 受影响正式件 doc_id
        - evidence_affected: 受影响测量证据
        - re_freeze_needed: bool
        - re_budget_needed: bool
        - re_comms_needed: bool
        - invalidated: 作废清单（list）
        - new_versions: 新版本号（dict）
    """
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

    # 关键门：必须 member + role
    if gate in GATE_DUAL_APPROVERS:
        if not member or not role:
            _fail(f"key gate {gate} requires member and role (dual approvers)")
        if role not in GATE_REQUIRED_ROLES.get(gate, ()):
            _fail(f"role {role} not allowed for {gate}; allowed={GATE_REQUIRED_ROLES.get(gate)}")

    # CHANGE 必带 change_payload
    if verdict == "CHANGE" and not change_payload:
        _fail("CHANGE requires change_payload with reason/affected_fields/etc")

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

    # 关键门累积 approvers；非关键门单签
    existing = state["gates"].get(gate) or {}
    approvers = list(existing.get("approvers") or [])
    if verdict in {"APPROVE", "REJECT"} and member and role:
        # 同 member+role 重复签 → fail；同 member 不同 role → 也 fail（关键门双签必须两人）
        if any(a.get("member") == member and a.get("role") == role for a in approvers):
            _fail(f"member {member}/{role} already signed {gate}")
        if gate in GATE_DUAL_APPROVERS and any(a.get("member") == member for a in approvers):
            _fail(f"member {member} already signed {gate}; key gate requires two distinct members")
        approvers.append({"member": member, "role": role, "at": now()})

    if gate in GATE_DUAL_APPROVERS and verdict == "APPROVE":
        required_roles = GATE_REQUIRED_ROLES.get(gate, ())
        got_roles = {a["role"] for a in approvers}
        if not required_roles[0] in got_roles or not required_roles[1] in got_roles:
            # 第一次：pending，不直接过门
            state["gates"][gate] = {
                "gate_id": f"{gate}/{state['case_id']}",
                "case_id": state["case_id"],
                "stage": state["stage"],
                "verdict": "PENDING_DUAL",
                "approvers": approvers,
                "required_outputs": list(required_outputs or []),
                "hard_check_results": dict(hard_check_results or {}),
                "quality_review_id": quality_review_id,
                "evidence_checksum": evidence_checksum,
                "decision_reason": decision_reason,
                "at": now(),
                "final": False,
            }
            state["log"].append({"at": now(), "op": "decide_partial", "gate": gate, "member": member, "role": role})
            return state

    # 单签门 OR 关键门第二次 / REJECT / CHANGE → 写最终 packet
    final_verdict = verdict
    is_final = True
    state["gates"][gate] = {
        "gate_id": f"{gate}/{state['case_id']}",
        "case_id": state["case_id"],
        "stage": state["stage"],
        "verdict": final_verdict,
        "approvers": approvers,
        "required_outputs": list(required_outputs or []),
        "hard_check_results": dict(hard_check_results or {}),
        "quality_review_id": quality_review_id,
        "evidence_checksum": evidence_checksum,
        "decision_reason": decision_reason,
        "at": now(),
        "final": is_final,
    }
    state["log"].append({"at": now(), "op": "decide", "gate": gate, "verdict": verdict, "member": member, "role": role})

    if verdict == "CHANGE":
        cp = dict(change_payload or {})
        cp["at"] = now()
        cp["gate"] = gate
        cp["stage"] = state["stage"]
        cp["rewind_to"] = rewind_to or state["stage"]
        state.setdefault("changes", []).append(cp)
        target = rewind_to or state["stage"]
        if target not in STAGES:
            _fail(f"bad rewind_to {target}")
        if STAGES.index(target) > STAGES.index(state["stage"]):
            _fail("cannot CHANGE forward")
        _clear_from(state, target, cases_root)
        return state

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
    return state


def status(state: dict) -> dict:
    nxt = next_action(state)
    nxt["fields"] = dict(state["fields"])
    nxt["gates"] = dict(state["gates"])
    return nxt
