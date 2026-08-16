#!/usr/bin/env python3
"""官方联网 API 哨兵：一次一问、不覆盖原始 JSON、幂等台账。不采集手机 App。"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import (
    ROOT,
    SAMPLE_FIELDS,
    case_ledger,
    case_sample_root,
    config_checksum,
    freeze_dir,
    load_table,
    require_case_ids,
    upsert_ledger,
)


def post_json(url: str, payload: dict, headers: dict) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def infer_search(channel: str, body: dict | str) -> str:
    if not isinstance(body, dict):
        return ""
    blob = json.dumps(body, ensure_ascii=False)
    if channel == "api_qwen_search":
        if "search_results" in blob or "search_info" in blob:
            return "1"
        return "0"
    if "web_search" in blob or "url_citation" in blob or "annotations" in blob:
        return "1"
    return ""


def call_qwen(text: str) -> tuple[dict, bool]:
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        return {"error": "missing DASHSCOPE_API_KEY"}, False
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    payload = {
        "model": os.environ.get("QWEN_MODEL", "qwen-plus"),
        "input": {"messages": [{"role": "user", "content": text}]},
        "parameters": {
            "enable_search": True,
            "search_options": {"forced_search": True, "enable_source": True},
        },
    }
    status, body = post_json(url, payload, {"Authorization": f"Bearer {key}"})
    ok = status == 200 and isinstance(body, dict) and "output" in body
    return {"http_status": status, "body": body}, ok


def call_deepseek(text: str) -> tuple[dict, bool]:
    """优先 Responses + web_search；旧 chat/completions 的 web_search tool 不可用。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        return {"error": "missing DEEPSEEK_API_KEY"}, False
    url = os.environ.get("DEEPSEEK_SEARCH_URL", "https://api.deepseek.com/responses")
    payload = {
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "input": text,
        "tools": [{"type": "web_search"}],
    }
    status, body = post_json(url, payload, {"Authorization": f"Bearer {key}"})
    ok = status == 200 and isinstance(body, dict)
    if not ok:
        return {
            "http_status": status,
            "body": body,
            "hint": "Chat Completions 不支持 type=web_search；请用官方 Responses 或关掉本通道",
        }, False
    return {"http_status": status, "body": body}, True


def call_doubao_search(text: str) -> tuple[dict, bool]:
    key = os.environ.get("ARK_API_KEY", "")
    endpoint = os.environ.get("DOUBAO_SEARCH_URL", "")
    if not key or not endpoint:
        return {"error": "missing ARK_API_KEY or DOUBAO_SEARCH_URL"}, False
    status, body = post_json(endpoint, {"query": text}, {"Authorization": f"Bearer {key}"})
    ok = status == 200 and isinstance(body, dict)
    return {"http_status": status, "body": body}, ok


CALLERS = {
    "api_qwen_search": call_qwen,
    "api_deepseek_search": call_deepseek,
    "api_doubao_search": call_doubao_search,
}


def unique_path(out_dir: Path, query_id: str, run_index: int, run_uuid: str) -> Path:
    preferred = out_dir / f"{query_id}_r{run_index}.json"
    if not preferred.exists():
        return preferred
    return out_dir / f"{query_id}_r{run_index}_{run_uuid[:8]}.json"


def run(
    day: str,
    channels: list[str],
    run_n: int,
    smoke: bool,
    include_explore: bool,
    freeze_id: str | None,
    task: str,
    case_id: str,
    project_id: str,
) -> None:
    require_case_ids(case_id, project_id)
    queries = [
        r
        for r in load_table("queries.csv", freeze_id, case_id=case_id)
        if r.get("active") == "1" and r.get("set") in ({"core", "holdout", "explore"} if include_explore else {"core", "holdout"})
    ]
    if smoke:
        queries = queries[:1]
        run_n = 1
    if not queries:
        raise SystemExit("冻结 queries 没有 active 的 core/holdout")
    proj = load_table("project.csv", freeze_id, case_id=case_id)
    frozen_pid = proj[0]["project_id"] if proj else ""
    if frozen_pid and frozen_pid != project_id:
        raise SystemExit(f"project_id 与冻结不符: {project_id} != {frozen_pid}")
    checksum = config_checksum(freeze_id, case_id=case_id)
    freeze_name = freeze_dir(freeze_id, case_id=case_id).name
    sample_root = case_sample_root(case_id)
    ledger = case_ledger(case_id)

    for channel in channels:
        if channel not in CALLERS:
            raise SystemExit(f"不支持的通道: {channel}")
        out_dir = sample_root / day / channel
        out_dir.mkdir(parents=True, exist_ok=True)
        caller = CALLERS[channel]
        for q in queries:
            for n in range(1, run_n + 1):
                run_uuid = uuid.uuid4().hex
                raw, ok = caller(q["text"])
                path = unique_path(out_dir, q["query_id"], n, run_uuid)
                parent = ""
                canon = out_dir / f"{q['query_id']}_r{n}.json"
                if path != canon and canon.exists():
                    parent = f"{day.replace('-', '')}_{channel}_{q['query_id']}_r{n}"
                record = {
                    "query_id": q["query_id"],
                    "text": q["text"],
                    "channel": channel,
                    "run_index": n,
                    "run_uuid": run_uuid,
                    "forced_search": 1,
                    "fresh_session": 1,
                    "ok": ok,
                    "response": raw,
                }
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                body = raw.get("body") if isinstance(raw, dict) else raw
                search = infer_search(channel, body if isinstance(body, dict) else raw)
                sample_id = f"{day.replace('-', '')}_{channel}_{q['query_id']}_r{n}"
                if path != canon:
                    sample_id = f"{sample_id}_{run_uuid[:8]}"
                status = upsert_ledger(
                    {
                        "sample_id": sample_id,
                        "date": day,
                        "query_id": q["query_id"],
                        "query_set": q["set"],
                        "treat": q.get("treat", ""),
                        "platform": channel.replace("api_", "").replace("_search", ""),
                        "channel": channel,
                        "run_index": str(n),
                        "city": q.get("locale", ""),
                        "logged_in": "0",
                        "fresh_session": "1",
                        "raw_json_path": str(path.relative_to(ROOT)),
                        "limited": "0" if ok else "1",
                        "notes": "" if ok else "api_failed",
                        "search_triggered": search,
                        "project_id": project_id,
                        "task": task,
                        "freeze_id": freeze_name,
                        "config_checksum": checksum,
                        "run_uuid": run_uuid,
                        "retry_of": parent,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    },
                    ledger_path=ledger,
                )
                print(f"{'OK' if ok else 'LIMITED'} {channel} {q['query_id']} r{n} {status}")
                time.sleep(1.2)


def main() -> None:
    p = argparse.ArgumentParser(description="GEO 官方 API 哨兵")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--channels", default="api_qwen_search")
    p.add_argument("--run-n", type=int, default=7)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--include-explore", action="store_true")
    p.add_argument("--freeze-id")
    p.add_argument("--task", default="weekly")
    p.add_argument("--case-id", dest="case_id", required=True)
    p.add_argument("--project-id", dest="project_id", required=True)
    args = p.parse_args()
    if args.run_n < 1:
        raise SystemExit("run-n 必须 >= 1")
    channels = [c.strip() for c in args.channels.split(";") if c.strip()]
    run(
        args.date,
        channels,
        args.run_n,
        args.smoke,
        args.include_explore,
        args.freeze_id,
        args.task,
        args.case_id,
        args.project_id,
    )


if __name__ == "__main__":
    main()
