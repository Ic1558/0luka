"""
multi_step_planner.py — Decomposes a user request into ordered, traceable, safe steps.

Invariants:
  - No execution — planning only
  - Destructive requests: blocked, step_count=0
  - review_required=True when plan_confidence < 0.6
  - All steps carry status="planned"

Output contract:
  {
    "task": str,
    "plan_id": str,
    "step_count": int,
    "steps": [
      {
        "step_id": str,
        "description": str,
        "intended_skill": str | None,
        "risk_hint": "low" | "medium" | "high" | "destructive" | "unknown",
        "status": "planned",
      }
    ],
    "plan_confidence": float,
    "review_required": bool,
  }
"""

import re
import uuid


_SKILL_PATTERNS = {
    "git_ops":    [r"\bgit\b", r"\bcommit\b", r"\bbranch\b", r"\bdiff\b",
                   r"\bmerge\b", r"\bpush\b", r"\bpull\b", r"\bstash\b", r"\bcheckout\b"],
    "file_ops":   [r"\bfile\b", r"\blist\b", r"\bread\b", r"\bwrite\b",
                   r"\bdirectory\b", r"\bfolder\b", r"\bls\b", r"\bpath\b"],
    "system_ops": [r"\bsystem\b", r"\bhealth\b", r"\bprocess\b", r"\bcpu\b",
                   r"\bdisk\b", r"\buptime\b", r"\bservice\b", r"\bcheck\b"],
    "analysis":   [r"\banalyze\b", r"\banalysis\b", r"\breport\b", r"\bpattern\b",
                   r"\binsight\b", r"\bsuggest\b", r"\bsummary\b"],
    "trading":    [r"\btrade\b", r"\btrading\b", r"\bposition\b", r"\bportfolio\b",
                   r"\bmarket\b"],
}

_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+-rf\b", r"\bdelete\s+all\b", r"\bdestroy\b", r"\bwipe\b",
    r"\bnuke\b", r"\bpurge\s+all\b",
]

_SKILL_STEPS = {
    "git_ops": [
        ("check_status",  "Check git repository status",   "low"),
        ("show_history",  "Show recent commit history",     "low"),
    ],
    "file_ops": [
        ("list_contents", "List directory contents",        "low"),
        ("read_files",    "Read target file contents",      "low"),
    ],
    "system_ops": [
        ("gather_metrics", "Gather system health metrics",  "low"),
        ("assess_health",  "Assess system health status",   "low"),
    ],
    "analysis": [
        ("gather_data",     "Gather data for analysis",               "low"),
        ("analyze_patterns","Analyze patterns in gathered data",      "low"),
        ("generate_findings","Generate structured findings report",   "low"),
    ],
    "trading": [
        ("fetch_positions",   "Fetch current trading positions",  "low"),
        ("evaluate_exposure", "Evaluate risk exposure",           "medium"),
    ],
}


def _is_destructive(text: str) -> bool:
    for p in _DESTRUCTIVE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _detect_skills(text: str) -> list:
    found = []
    text_lower = text.lower()
    for skill, patterns in _SKILL_PATTERNS.items():
        for p in patterns:
            if re.search(p, text_lower):
                found.append(skill)
                break
    return found


def create_plan(task) -> dict:
    """
    Decompose a task into an ordered, traceable, safe plan.

    Args:
        task: str or dict with "intent" or "task" key.

    Returns:
        Structured plan dict.
    """
    if isinstance(task, dict):
        text = task.get("intent") or task.get("task") or str(task)
    else:
        text = str(task)

    plan_id = str(uuid.uuid4())[:8]

    if _is_destructive(text):
        return {
            "task": text,
            "plan_id": plan_id,
            "step_count": 0,
            "steps": [],
            "plan_confidence": 0.0,
            "review_required": True,
            "blocked": True,
            "blocked_reason": "destructive_intent — planning refused",
        }

    skills = _detect_skills(text)
    raw_steps = []
    seen = set()

    for skill in skills:
        for (action, desc, risk) in _SKILL_STEPS.get(skill, []):
            key = (skill, desc)
            if key not in seen:
                seen.add(key)
                raw_steps.append({
                    "description": desc,
                    "intended_skill": skill,
                    "risk_hint": risk,
                    "status": "planned",
                })

    if not raw_steps:
        raw_steps.append({
            "description": f"Execute: {text[:80]}",
            "intended_skill": None,
            "risk_hint": "unknown",
            "status": "planned",
        })

    steps = []
    for i, s in enumerate(raw_steps, 1):
        steps.append({"step_id": f"step_{i}", **s})

    confidence = 0.8 if skills else 0.4
    review_required = confidence < 0.6

    return {
        "task": text,
        "plan_id": plan_id,
        "step_count": len(steps),
        "steps": steps,
        "plan_confidence": confidence,
        "review_required": review_required,
    }
