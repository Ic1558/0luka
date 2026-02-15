from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class EmailOrchestrationConfig:
    imap_host: str = os.getenv("LUKA_IMAP_HOST", "")
    imap_port: int = int(os.getenv("LUKA_IMAP_PORT", "993"))
    imap_user: str = os.getenv("LUKA_IMAP_USER", "")
    imap_password: str = os.getenv("LUKA_IMAP_PASSWORD", "")
    smtp_host: str = os.getenv("LUKA_SMTP_HOST", "")
    smtp_port: int = int(os.getenv("LUKA_SMTP_PORT", "587"))
    smtp_user: str = os.getenv("LUKA_SMTP_USER", "")
    smtp_password: str = os.getenv("LUKA_SMTP_PASSWORD", "")
    redis_url: str = os.getenv("LUKA_REDIS_URL", "redis://127.0.0.1:6379/0")
    request_channel: str = os.getenv("LUKA_REQUEST_CHANNEL", "gg:requests")
    response_prefix: str = os.getenv("LUKA_RESPONSE_PREFIX", "gg:responses")
    command_token: str = os.getenv("LUKA_COMMAND_TOKEN", "")
    repo_root: Path = Path(os.getenv("LUKA_REPO_ROOT", Path(__file__).resolve().parents[2]))
    allowed_domains: List[str] = field(
        default_factory=lambda: [x.strip().lower() for x in os.getenv("LUKA_ALLOWED_DOMAINS", "theedges.com").split(",") if x.strip()]
    )
    allowed_senders: List[str] = field(
        default_factory=lambda: [x.strip().lower() for x in os.getenv("LUKA_ALLOWED_SENDERS", "luka.ai@theedges.com").split(",") if x.strip()]
    )
    ring_to_lane: Dict[str, str] = field(
        default_factory=lambda: {
            "R0": "observe",
            "R1": "assist",
            "R2": "execute",
            "R3": "governed",
        }
    )


def load_config() -> EmailOrchestrationConfig:
    return EmailOrchestrationConfig()
