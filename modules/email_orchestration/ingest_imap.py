from __future__ import annotations

import email
import imaplib
from email.message import EmailMessage
from typing import List, Tuple


def pull_unseen(imap_host: str, imap_port: int, imap_user: str, imap_password: str) -> List[Tuple[bytes, EmailMessage]]:
    out: List[Tuple[bytes, EmailMessage]] = []
    with imaplib.IMAP4_SSL(imap_host, imap_port) as imap:
        imap.login(imap_user, imap_password)
        imap.select("INBOX")
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return out
        for msg_id in data[0].split():
            st, msg_data = imap.fetch(msg_id, "(RFC822)")
            if st != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            raw = msg_data[0][1]
            parsed = email.message_from_bytes(raw)
            if isinstance(parsed, EmailMessage):
                out.append((raw, parsed))
            else:
                out.append((raw, email.message_from_bytes(raw, _class=EmailMessage)))
    return out
