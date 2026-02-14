from __future__ import annotations

import argparse
import json
import logging
import time
from email import message_from_bytes
from email.message import EmailMessage
from pathlib import Path

from .config import load_config
from .dispatch import dispatch_via_redis
from .evidence import evidence_paths, write_json, write_parsed_yaml, write_raw_eml
from .ingest_imap import pull_unseen
from .parse_command import parse_message
from .reply_smtp import render_reply, send_reply
from .route import route_task
from .validate import validate_email


def _logger(repo_root: Path) -> logging.Logger:
    p = repo_root / "observability" / "logs" / "email_orchestrator.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("email_orchestrator")
    if not logger.handlers:
        handler = logging.FileHandler(p)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def process_one(raw: bytes, msg: EmailMessage, cfg) -> dict:
    parsed = parse_message(msg)
    task_id = str(parsed.get("task_id") or f"mail-{int(time.time())}")
    paths = evidence_paths(cfg.repo_root, task_id)
    sha = write_raw_eml(paths, raw)
    write_parsed_yaml(paths, json.dumps(parsed, indent=2, sort_keys=True))

    ok, verdict = validate_email(msg, parsed, cfg.allowed_domains, cfg.allowed_senders, cfg.command_token)
    verdict["sha256"] = sha
    write_json(paths, "verdict", verdict)

    if not ok:
        result = {"status": "REJECT", "exit_code": 1, "report_paths": {k: str(v) for k, v in paths.items() if k != "run_dir"}}
        write_json(paths, "result", result)
        return {"task_id": task_id, "status": "REJECT", "paths": paths, "verdict": verdict, "result": result}

    route = route_task(parsed, cfg.request_channel)
    payload = dict(parsed)
    payload["task_id"] = task_id
    payload["redis_url"] = cfg.redis_url
    dispatch = dispatch_via_redis(payload, route["request_channel"], route["response_channel"])
    dispatch["report_paths"] = {k: str(v) for k, v in paths.items() if k != "run_dir"}
    write_json(paths, "result", dispatch)
    return {"task_id": task_id, "status": dispatch.get("status", "FAILED"), "paths": paths, "verdict": verdict, "result": dispatch}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest-once", "run-loop", "validate-only", "reply-test"])
    parser.add_argument("--eml", help="Path to local .eml for validate-only")
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    cfg = load_config()
    log = _logger(cfg.repo_root)

    if args.command == "validate-only":
        if not args.eml:
            raise SystemExit("--eml required for validate-only")
        raw = Path(args.eml).read_bytes()
        msg = message_from_bytes(raw, _class=EmailMessage)
        out = process_one(raw, msg, cfg)
        print(json.dumps({"task_id": out["task_id"], "status": out["status"]}, sort_keys=True))
        return 0

    if args.command == "reply-test":
        body = render_reply("DONE", "task-reply-test", {"ok": True}, {"exit_code": 0}, {"result": "observability/email_runs/.../result.json"})
        print(body)
        return 0

    if args.command == "ingest-once":
        items = pull_unseen(cfg.imap_host, cfg.imap_port, cfg.imap_user, cfg.imap_password)
        for raw, msg in items:
            out = process_one(raw, msg, cfg)
            log.info(json.dumps({"event": "processed", "task_id": out["task_id"], "status": out["status"]}, sort_keys=True))
        return 0

    while True:
        items = pull_unseen(cfg.imap_host, cfg.imap_port, cfg.imap_user, cfg.imap_password)
        for raw, msg in items:
            out = process_one(raw, msg, cfg)
            log.info(json.dumps({"event": "processed", "task_id": out["task_id"], "status": out["status"]}, sort_keys=True))
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
