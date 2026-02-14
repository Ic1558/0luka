from email.message import EmailMessage

from modules.email_orchestration.validate import validate_email


def _msg() -> EmailMessage:
    m = EmailMessage()
    m["From"] = "Luka AI <luka.ai@theedges.com>"
    m["Authentication-Results"] = "mx; dkim=pass"
    return m


def test_validate_rejects_missing_ring():
    msg = _msg()
    ok, verdict = validate_email(msg, {"task_id": "x", "auth.token": "abc"}, ["theedges.com"], ["luka.ai@theedges.com"], "abc")
    assert not ok
    assert "ring_missing_or_invalid" in verdict["reasons"]


def test_validate_rejects_missing_token():
    msg = _msg()
    ok, verdict = validate_email(msg, {"task_id": "x", "ring": "R2"}, ["theedges.com"], ["luka.ai@theedges.com"], "abc")
    assert not ok
    assert "token_missing_or_invalid" in verdict["reasons"]
