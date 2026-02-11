#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_KEYS = {
    "id": str,
    "version": int,
    "regex": str,
    "replacement": str,
    "score_weight": (int, float),
    "tags": list,
    "enabled": bool,
}


@dataclass(frozen=True)
class Pattern:
    id: str
    version: int
    regex: str
    replacement: str
    score_weight: float
    tags: tuple[str, ...]
    enabled: bool


def _load_text(input_file: str | None) -> str:
    if input_file:
        return Path(input_file).read_text(encoding="utf-8")
    return sys.stdin.read()


def _validate_row(row: dict[str, Any], line_no: int) -> None:
    for key, typ in REQUIRED_KEYS.items():
        if key not in row:
            raise ValueError(f"invalid_pattern_line:{line_no}:missing:{key}")
        if not isinstance(row[key], typ):
            raise ValueError(f"invalid_pattern_line:{line_no}:type:{key}")
    if not row["id"]:
        raise ValueError(f"invalid_pattern_line:{line_no}:empty:id")
    if row["score_weight"] < 0:
        raise ValueError(f"invalid_pattern_line:{line_no}:negative:score_weight")


def load_patterns(patterns_path: str) -> list[Pattern]:
    out: list[Pattern] = []
    p = Path(patterns_path)
    for idx, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_pattern_line:{idx}:json:{exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"invalid_pattern_line:{idx}:root_not_object")
        _validate_row(row, idx)
        out.append(
            Pattern(
                id=row["id"],
                version=row["version"],
                regex=row["regex"],
                replacement=row["replacement"],
                score_weight=float(row["score_weight"]),
                tags=tuple(str(t) for t in row["tags"]),
                enabled=row["enabled"],
            )
        )
    # deterministic processing order
    out.sort(key=lambda ptn: ptn.id)
    return out


def detect(text: str, patterns: list[Pattern]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for ptn in patterns:
        if not ptn.enabled:
            continue
        regex = re.compile(ptn.regex)
        for m in regex.finditer(text):
            matches.append(
                {
                    "pattern_id": ptn.id,
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(0),
                    "replacement": ptn.replacement,
                    "score_weight": ptn.score_weight,
                    "tags": list(ptn.tags),
                }
            )
    matches.sort(key=lambda m: (m["start"], m["end"], m["pattern_id"]))
    return {
        "command": "detect",
        "match_count": len(matches),
        "matched_pattern_ids": sorted({m["pattern_id"] for m in matches}),
        "matches": matches,
    }


def _apply_rewrite_once(text: str, ptn: Pattern) -> tuple[str, int]:
    regex = re.compile(ptn.regex)
    rewritten, n = regex.subn(ptn.replacement, text)
    return rewritten, n


def rewrite(text: str, patterns: list[Pattern]) -> dict[str, Any]:
    rewritten = text
    changes_applied: list[dict[str, Any]] = []
    for ptn in patterns:
        if not ptn.enabled:
            continue
        rewritten_next, count = _apply_rewrite_once(rewritten, ptn)
        if count > 0:
            changes_applied.append(
                {
                    "pattern_id": ptn.id,
                    "count": count,
                    "replacement": ptn.replacement,
                }
            )
        rewritten = rewritten_next
    return {
        "command": "rewrite",
        "changes_applied": changes_applied,
        "matched_pattern_ids": sorted({c["pattern_id"] for c in changes_applied}),
        "rewritten_text": rewritten,
    }


def score(text: str, patterns: list[Pattern]) -> dict[str, Any]:
    det = detect(text, patterns)
    total = 0.0
    for m in det["matches"]:
        total += float(m["score_weight"])
    # stable numeric precision for downstream comparisons
    total = round(total, 6)
    return {
        "command": "score",
        "score": total,
        "match_count": det["match_count"],
        "matched_pattern_ids": det["matched_pattern_ids"],
    }


def _atomic_write(path: str, content: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(out.parent)) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, out)


def _print(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="pattern-killer deterministic CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--patterns", required=True)
        p.add_argument("--input-file")

    p_detect = sub.add_parser("detect")
    add_common(p_detect)

    p_score = sub.add_parser("score")
    add_common(p_score)

    p_rewrite = sub.add_parser("rewrite")
    add_common(p_rewrite)
    p_rewrite.add_argument("--apply", action="store_true")
    p_rewrite.add_argument("--output-file")

    args = parser.parse_args()

    patterns = load_patterns(args.patterns)
    text = _load_text(args.input_file)

    if args.command == "detect":
        _print(detect(text, patterns))
        return 0

    if args.command == "score":
        _print(score(text, patterns))
        return 0

    result = rewrite(text, patterns)
    if args.apply:
        if not args.output_file:
            raise ValueError("rewrite_apply_requires_output_file")
        _atomic_write(args.output_file, result["rewritten_text"])
        result["applied"] = True
        result["output_file"] = str(Path(args.output_file))
    else:
        result["applied"] = False
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
