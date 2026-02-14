from __future__ import annotations

import re
from email.message import EmailMessage
from typing import Any, Dict, List


SUBJECT_RE = re.compile(r"^\[LUKA\]\[(R[0-3])\]\[(\w+)\]\s+(.+?)(?:\s+#([\w\-]+))?$")


def extract_numbered_steps(text: str) -> List[str]:
    steps: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(r"^\d+[\.)]\s+(.*)$", stripped)
        if m:
            steps.append(m.group(1).strip())
    return steps


def parse_yaml_body(yaml_body: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    steps: List[str] = []
    in_steps = False
    for raw in yaml_body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.strip().startswith("#"):
            continue
        if re.match(r"^\s*steps\s*:\s*$", line):
            in_steps = True
            result["steps"] = steps
            continue
        if in_steps and re.match(r"^\s*[-]\s+", line):
            steps.append(re.sub(r"^\s*[-]\s+", "", line).strip())
            continue
        in_steps = False
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value.lower() in {"true", "false"}:
                result[key] = value.lower() == "true"
            else:
                result[key] = value.strip('"\'')
    if not result.get("steps"):
        numbered = extract_numbered_steps(yaml_body)
        if numbered:
            result["steps"] = numbered
    return result


def parse_message(message: EmailMessage) -> Dict[str, Any]:
    subject = message.get("Subject", "").strip()
    subject_match = SUBJECT_RE.match(subject)
    subject_data: Dict[str, Any] = {}
    if subject_match:
        subject_data = {
            "ring": subject_match.group(1),
            "verb": subject_match.group(2),
            "title": subject_match.group(3).strip(),
            "subject_task_id": subject_match.group(4),
        }

    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                break
    else:
        body = message.get_payload(decode=True).decode(message.get_content_charset() or "utf-8", errors="replace")

    payload = parse_yaml_body(body)
    if "ring" not in payload and subject_data.get("ring"):
        payload["ring"] = subject_data["ring"]
    if "task_id" not in payload and subject_data.get("subject_task_id"):
        payload["task_id"] = subject_data["subject_task_id"]
    payload.setdefault("title", subject_data.get("title", ""))
    payload.setdefault("verb", subject_data.get("verb", ""))
    return payload
