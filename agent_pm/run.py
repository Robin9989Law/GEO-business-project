#!/usr/bin/env python3
"""Agent PM CLI。人只跑 decide / pick / ack；其余是 Agent。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
import files
import review
import teaching


def _print(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _root(args) -> Path | None:
    return Path(args.cases_root) if args.cases_root else None


def _files_root(args) -> Path | None:
    return Path(args.files_root) if getattr(args, "files_root", "") else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GEO Agent 项目管理")
    p.add_argument(
        "cmd",
        choices=(
            "init",
            "next",
            "apply",
            "decide",
            "status",
            "guide",
            "deposit",
            "promote",
            "checkout",
            "checkin",
            "drop",
            "pick",
            "ack",
            "board",
            "check-vault",
            "profile",
            "review",
            "appeal",
            "resolve-review",
        ),
    )
    p.add_argument("case_id")
    p.add_argument("--json", dest="json_path")
    p.add_argument("--raw", action="store_true", help="next/guide 输出 JSON 而不是中文说明书")
    p.add_argument("--gate")
    p.add_argument("--verdict", choices=("APPROVE", "REJECT", "CHANGE", "UPHOLD", "OVERRIDE_SOFT"))
    p.add_argument("--actor", default="")
    p.add_argument("--cases-root", default="")
    p.add_argument("--files-root", default="")
    p.add_argument("--src", default="")
    p.add_argument("--stage", default="")
    p.add_argument("--title", default="")
    p.add_argument("--doc-id", dest="doc_id", default="")
    p.add_argument("--member", default="")
    p.add_argument("--role", default="")
    p.add_argument("--decision-reason", dest="decision_reason", default="")
    p.add_argument("--change-json", dest="change_json", default="")
    p.add_argument("--from", dest="sender", default="")
    p.add_argument("--to", dest="receiver", default="")
    p.add_argument("--item", default="")
    p.add_argument("--note", default="")
    p.add_argument("--rewind", dest="rewind_to", default="")
    p.add_argument("--raw-id", dest="raw_id", default="")
    p.add_argument("--review-id", dest="review_id", default="")
    p.add_argument("--reason", default="")
    args = p.parse_args(argv)
    root = _root(args)
    froot = _files_root(args)
    state = None
    try:
        if args.cmd == "init":
            _print(engine.init_case(args.case_id, root))
            return 0
        if args.cmd == "deposit":
            if not args.src:
                raise SystemExit("deposit needs --src")
            stage = args.stage or engine.load_state(args.case_id, root)["stage"]
            _print(
                files.deposit_raw(
                    args.case_id,
                    args.src,
                    stage,
                    title=args.title,
                    actor=args.actor or "agent",
                    cases_root=root,
                    files_root=froot,
                )
            )
            return 0
        if args.cmd == "promote":
            if not args.src or not args.doc_id:
                raise SystemExit("promote needs --src and --doc-id")
            st = engine.load_state(args.case_id, root)
            _print(
                files.promote_formal(
                    args.case_id,
                    args.src,
                    args.doc_id,
                    gate=args.gate or "",
                    stage=args.stage or st["stage"],
                    title=args.title,
                    cases_root=root,
                    files_root=froot,
                )
            )
            return 0
        if args.cmd == "checkout":
            if not args.doc_id or not args.member:
                raise SystemExit("checkout needs --doc-id and --member")
            _print(files.checkout(args.case_id, args.doc_id, args.member, note=args.note, cases_root=root, files_root=froot))
            return 0
        if args.cmd == "checkin":
            if not args.doc_id or not args.src or not args.member:
                raise SystemExit("checkin needs --doc-id --src --member")
            st = engine.load_state(args.case_id, root)
            _print(
                files.checkin(
                    args.case_id,
                    args.doc_id,
                    args.src,
                    args.member,
                    gate=args.gate or "",
                    stage=args.stage or st["stage"],
                    cases_root=root,
                    files_root=froot,
                )
            )
            return 0
        if args.cmd == "drop":
            if not args.src or not args.sender or not args.receiver:
                raise SystemExit("drop needs --src --from --to")
            _print(
                files.drop_exchange(
                    args.case_id,
                    args.src,
                    args.sender,
                    args.receiver,
                    note=args.note,
                    cases_root=root,
                    files_root=froot,
                )
            )
            return 0
        if args.cmd == "pick":
            if not args.item or not args.member:
                raise SystemExit("pick needs --item and --member")
            _print(files.pick_exchange(args.case_id, args.item, args.member, cases_root=root, files_root=froot))
            return 0
        if args.cmd == "ack":
            if not args.item or not args.member:
                raise SystemExit("ack needs --item and --member")
            _print(files.ack_exchange(args.case_id, args.item, args.member, cases_root=root, files_root=froot))
            return 0
        if args.cmd == "board":
            b = files.board(args.case_id, cases_root=root, files_root=froot)
            if args.raw:
                _print(b)
            else:
                print(files.format_board(b))
            return 0
        if args.cmd == "check-vault":
            if args.case_id in {"ALL", "*", "."}:
                report = files.check_all_vaults(cases_root=root, files_root=froot)
            else:
                report = files.check_vault(args.case_id, cases_root=root, files_root=froot)
            _print(report)
            return 0 if report.get("ok") else 1
        state = engine.load_state(args.case_id, root)
        teaching.ensure_process(state)
        if args.cmd == "profile":
            if not args.member:
                raise SystemExit("profile needs --member")
            if not args.json_path:
                raise SystemExit("profile needs --json")
            payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
            rec = teaching.set_profile(state, args.member, payload)
            engine.save_state(state, root)
            _print(rec)
            return 0
        if args.cmd == "review":
            if not args.json_path:
                raise SystemExit("review needs --json")
            payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
            rec = review.submit_review(
                state,
                payload,
                member=args.member,
                raw_id=args.raw_id,
                cases_root=root,
                files_root=froot,
            )
            engine.save_state(state, root)
            _print(rec)
            return 0
        if args.cmd == "appeal":
            if not args.review_id:
                raise SystemExit("appeal needs --review-id")
            rec = review.appeal(state, args.review_id, args.reason, cases_root=root, files_root=froot)
            engine.save_state(state, root)
            _print(rec)
            return 0
        if args.cmd == "resolve-review":
            if not args.review_id or args.verdict not in {"UPHOLD", "OVERRIDE_SOFT"}:
                raise SystemExit("resolve-review needs --review-id and --verdict UPHOLD|OVERRIDE_SOFT")
            rec = review.resolve_review(
                state,
                args.review_id,
                args.verdict,
                actor=args.actor or "human",
                reason=args.reason,
                cases_root=root,
                files_root=froot,
            )
            engine.save_state(state, root)
            _print(rec)
            return 0
        if args.cmd in {"next", "guide"}:
            nxt = engine.next_action(state)
            if args.raw:
                _print(nxt)
            else:
                print(nxt.get("briefing") or "")
            return 0
        if args.cmd == "status":
            _print(engine.status(state))
            return 0
        if args.cmd == "apply":
            if not args.json_path:
                raise SystemExit("apply needs --json")
            payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
            engine.apply_fields(state, payload, actor="agent", cases_root=root)
            files.deposit_inbox(args.case_id, state["stage"], cases_root=root, files_root=froot)
            engine.save_state(state, root)
            _print(engine.next_action(state))
            return 0
        if args.cmd == "decide":
            if not args.gate or not args.verdict:
                raise SystemExit("decide needs --gate and --verdict")
            actor = args.actor or "human"
            change_payload = None
            if args.change_json:
                change_payload = json.loads(Path(args.change_json).read_text(encoding="utf-8"))
            elif args.verdict == "CHANGE" and args.json_path:
                blob = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
                change_payload = blob.get("change_payload") or blob
            engine.decide(
                state,
                args.gate,
                args.verdict,
                actor=actor,
                cases_root=root,
                rewind_to=args.rewind_to or None,
                member=args.member,
                role=args.role,
                decision_reason=args.decision_reason,
                change_payload=change_payload,
            )
            engine.save_state(state, root)
            _print(engine.next_action(state))
            return 0
    except review.ReviewTargetStale as e:
        if state is not None:
            engine.save_state(state, root)
        print(str(e), file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError, FileExistsError) as e:
        print(str(e), file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
