#!/usr/bin/env python3
import json
import os
import sys
import urllib.request


def _fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    base = os.environ.get("OPAL_API_BASE", "http://127.0.0.1:7001").rstrip("/")

    spec = _fetch_json(f"{base}/openapi.json")
    paths = spec.get("paths", {})
    pj = paths.get("/api/jobs", {})
    if "get" not in pj:
        print("FAIL: openapi.json missing GET /api/jobs", file=sys.stderr)
        return 2

    # Contract expectation: GET /api/jobs returns an object/map
    resp200 = (((pj.get("get") or {}).get("responses") or {}).get("200") or {})
    schema = (((resp200.get("content") or {}).get("application/json") or {}).get("schema") or {})
    expected = schema.get("type")
    if expected != "object":
        print(
            f"FAIL: contract expects type={expected!r} for GET /api/jobs (expected 'object')",
            file=sys.stderr,
        )
        return 3

    data = _fetch_json(f"{base}/api/jobs")
    if not isinstance(data, dict):
        print(
            f"FAIL: runtime /api/jobs returned {type(data).__name__}, expected dict/object",
            file=sys.stderr,
        )
        return 4

    # Minimal required fields from JobDetail schema (id, status)
    for job_id, job in list(data.items())[:50]:
        if not isinstance(job, dict):
            print(
                f"FAIL: job {job_id} value is {type(job).__name__}, expected object",
                file=sys.stderr,
            )
            return 5
        if "id" not in job or "status" not in job:
            print(
                f"FAIL: job {job_id} missing required fields (id/status)",
                file=sys.stderr,
            )
            return 6

    print("OK: contract and runtime agree for GET /api/jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
