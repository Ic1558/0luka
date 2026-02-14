from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Dict


def send_reply(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str, to_addr: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)


def render_reply(status: str, task_id: str, verdict: Dict, result: Dict, proof_paths: Dict[str, str]) -> str:
    return (
        f"status: {status}\n"
        f"task_id: {task_id}\n"
        f"verdict_ok: {verdict.get('ok')}\n"
        f"exit_code: {result.get('exit_code')}\n"
        f"report_paths: {proof_paths}\n"
    )
