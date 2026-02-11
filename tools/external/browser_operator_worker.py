#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

MODULE_NAME = "browser_op"


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json_dumps(payload))
        handle.write("\n")


def sanitize_error(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def validate_url(url: str, constraints: Dict[str, Any]) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Only https URLs are permitted.")
    if parsed.scheme.lower() in {"file", "chrome", "data", "javascript"}:
        raise ValueError("Blocked URL scheme.")
    if constraints.get("allow_https_only", True) and parsed.scheme.lower() != "https":
        raise ValueError("HTTPS-only mode enforced.")
    allow_hosts = constraints.get("allow_hosts")
    if allow_hosts:
        hostname = parsed.hostname or ""
        if hostname not in allow_hosts:
            raise ValueError(f"Host '{hostname}' is not in allowlist.")


def map_key(key: str) -> str:
    mapping = {
        "CTRL": Keys.CONTROL,
        "CONTROL": Keys.CONTROL,
        "SHIFT": Keys.SHIFT,
        "ALT": Keys.ALT,
        "OPTION": Keys.ALT,
        "CMD": Keys.COMMAND,
        "COMMAND": Keys.COMMAND,
        "META": Keys.META,
        "ENTER": Keys.ENTER,
        "RETURN": Keys.RETURN,
        "TAB": Keys.TAB,
        "ESC": Keys.ESCAPE,
        "ESCAPE": Keys.ESCAPE,
        "BACKSPACE": Keys.BACKSPACE,
        "DELETE": Keys.DELETE,
        "SPACE": Keys.SPACE,
        "UP": Keys.ARROW_UP,
        "DOWN": Keys.ARROW_DOWN,
        "LEFT": Keys.ARROW_LEFT,
        "RIGHT": Keys.ARROW_RIGHT,
        "HOME": Keys.HOME,
        "END": Keys.END,
        "PAGE_UP": Keys.PAGE_UP,
        "PAGE_DOWN": Keys.PAGE_DOWN,
    }
    normalized = key.strip().upper()
    if "+" in normalized:
        parts = [map_key(part) for part in normalized.split("+")]
        return Keys.chord(*parts)
    return mapping.get(normalized, key)


def build_driver(mode: str, profile_dir: Path, debugger_address: str, headless: bool) -> webdriver.Chrome:
    options = ChromeOptions()
    if mode == "bot_profile":
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        if headless:
            options.add_argument("--headless=new")
        return webdriver.Chrome(options=options)

    if mode == "attach_user_chrome":
        options.debugger_address = debugger_address
        return webdriver.Chrome(options=options)

    raise ValueError(f"Unsupported mode: {mode}")


def handle_steps(
    driver: webdriver.Chrome,
    steps: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    artifacts_dir: Path,
    artifact_prefix: str,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    artifact_paths: List[str] = []
    ok = True
    error: Optional[str] = None

    for index, step in enumerate(steps):
        action = step.get("action") or step.get("type")
        step_result: Dict[str, Any] = {
            "index": index,
            "action": action,
            "ok": True,
        }
        try:
            if action == "open_url":
                url = step["url"]
                validate_url(url, constraints)
                driver.get(url)
            elif action == "click":
                selector = step["selector"]
                driver.find_element(By.CSS_SELECTOR, selector).click()
            elif action == "fill":
                selector = step["selector"]
                text = step.get("text", "")
                element = driver.find_element(By.CSS_SELECTOR, selector)
                element.clear()
                element.send_keys(text)
            elif action == "press":
                key_value = step["key"]
                driver.switch_to.active_element.send_keys(map_key(key_value))
            elif action == "wait_for":
                selector = step.get("selector")
                timeout = float(step.get("timeout", 10))
                if selector:
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                else:
                    time.sleep(timeout)
            elif action == "screenshot":
                filename = f"{artifact_prefix}_screenshot_{index}.png"
                path = artifacts_dir / filename
                ensure_dir(path.parent)
                driver.save_screenshot(str(path))
                artifact_paths.append(str(path))
                step_result["artifact"] = str(path)
            else:
                raise ValueError(f"Unknown action: {action}")
        except Exception as exc:  # noqa: BLE001 - capture all step errors
            ok = False
            error = sanitize_error(exc)
            step_result["ok"] = False
            step_result["error"] = error
            failure_name = f"{artifact_prefix}_failure_{index}.png"
            failure_path = artifacts_dir / failure_name
            try:
                ensure_dir(failure_path.parent)
                driver.save_screenshot(str(failure_path))
                artifact_paths.append(str(failure_path))
                step_result["failure_screenshot"] = str(failure_path)
            except Exception as screenshot_exc:  # noqa: BLE001
                step_result["failure_screenshot_error"] = sanitize_error(screenshot_exc)
            results.append(step_result)
            break

        results.append(step_result)

    return {
        "ok": ok,
        "error": error,
        "steps": results,
        "artifact_paths": artifact_paths,
    }


def build_artifact_prefix(task_ts: str, task_id: str) -> str:
    return f"{task_ts}_browser_op_{task_id}"


def write_result_md(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        f"# Browser Operator Result ({payload['task_id']})",
        "",
        f"Status: {'OK' if payload['ok'] else 'ERROR'}",
        f"Mode: {payload['mode']}",
        f"Timestamp: {payload['ts']}",
        "",
    ]
    if payload.get("error"):
        lines.extend(["## Error", payload["error"], ""])
    lines.append("## Artifacts")
    for artifact in payload.get("artifact_paths", []):
        lines.append(f"- {artifact}")
    lines.append("")
    ensure_dir(path.parent)
    path.write_text("\n".join(lines), encoding="utf-8")


def process_task(task_path: Path, root: Path) -> None:
    inbox_dir = root / "observability" / "bridge" / "inbox" / MODULE_NAME
    outbox_dir = root / "observability" / "bridge" / "outbox" / MODULE_NAME
    artifacts_dir = root / "observability" / "artifacts" / MODULE_NAME
    telemetry_path = root / "observability" / "telemetry" / f"{MODULE_NAME}.latest.json"
    ledger_path = root / "observability" / "stl" / "ledger" / "global_beacon.jsonl"
    processed_dir = inbox_dir / "processed"
    ensure_dir(processed_dir)

    task: Dict[str, Any] = {}
    task_id = task_path.stem
    task_ts = utc_ts()
    mode = "bot_profile"
    steps: List[Dict[str, Any]] = []
    constraints: Dict[str, Any] = {}

    try:
        task = load_json(task_path)
        task_id = task.get("task_id") or task_id
        task_ts = task.get("ts") or task_ts
        mode = task.get("mode", mode)
        steps = task.get("steps", steps)
        constraints = task.get("constraints", constraints)
    except Exception as exc:  # noqa: BLE001 - capture invalid task payloads
        error_payload = {
            "task_id": task_id,
            "ts": task_ts,
            "mode": mode,
            "ok": False,
            "error": f"Invalid task payload: {sanitize_error(exc)}",
            "steps": [],
            "constraints": {},
        }
        trace_path = artifacts_dir / f"{build_artifact_prefix(task_ts, task_id)}_trace.json"
        result_md_path = artifacts_dir / f"{build_artifact_prefix(task_ts, task_id)}_result.md"
        save_json(trace_path, error_payload)
        result_payload = {
            **error_payload,
            "artifact_paths": [str(trace_path), str(result_md_path)],
        }
        result_path = outbox_dir / f"{task_id}.result.json"
        save_json(result_path, result_payload)
        write_result_md(result_md_path, result_payload)
        telemetry_payload = {
            "ts": utc_ts(),
            "module": MODULE_NAME,
            "status": "error",
            "task_id": task_id,
            "mode": mode,
            "artifact_paths": result_payload["artifact_paths"],
        }
        save_json(telemetry_path, telemetry_payload)
        ledger_payload = {
            "ts": utc_ts(),
            "module": MODULE_NAME,
            "event": "task_completed",
            "task_id": task_id,
            "mode": mode,
            "ok": False,
        }
        append_jsonl(ledger_path, ledger_payload)
        processed_path = processed_dir / task_path.name
        shutil.move(str(task_path), str(processed_path))
        return

    artifact_prefix = build_artifact_prefix(task_ts, task_id)
    trace_path = artifacts_dir / f"{artifact_prefix}_trace.json"
    result_md_path = artifacts_dir / f"{artifact_prefix}_result.md"

    profile_dir = root / "runtime" / "browser_operator_profile"
    debugger_address = os.environ.get("BROWSER_OP_DEBUGGER_ADDRESS", "127.0.0.1:9222")
    headless = os.environ.get("BROWSER_OP_HEADLESS", "1") == "1"

    driver: Optional[webdriver.Chrome] = None
    ok = False
    error: Optional[str] = None
    step_results: List[Dict[str, Any]] = []
    artifact_paths: List[str] = []

    try:
        driver = build_driver(mode, profile_dir, debugger_address, headless)
        execution = handle_steps(driver, steps, constraints, artifacts_dir, artifact_prefix)
        ok = execution["ok"]
        error = execution["error"]
        step_results = execution["steps"]
        artifact_paths = execution["artifact_paths"]
    except (ValueError, TimeoutException, WebDriverException) as exc:
        ok = False
        error = sanitize_error(exc)
    finally:
        if driver:
            driver.quit()

    trace_payload = {
        "task_id": task_id,
        "ts": task_ts,
        "mode": mode,
        "ok": ok,
        "error": error,
        "steps": step_results,
        "constraints": constraints,
    }
    save_json(trace_path, trace_payload)

    result_payload = {
        "task_id": task_id,
        "ts": task_ts,
        "mode": mode,
        "ok": ok,
        "error": error,
        "steps": step_results,
        "artifact_paths": [str(trace_path), str(result_md_path), *artifact_paths],
    }
    result_path = outbox_dir / f"{task_id}.result.json"
    save_json(result_path, result_payload)
    write_result_md(result_md_path, result_payload)

    telemetry_payload = {
        "ts": utc_ts(),
        "module": MODULE_NAME,
        "status": "ok" if ok else "error",
        "task_id": task_id,
        "mode": mode,
        "artifact_paths": result_payload["artifact_paths"],
    }
    save_json(telemetry_path, telemetry_payload)

    ledger_payload = {
        "ts": utc_ts(),
        "module": MODULE_NAME,
        "event": "task_completed",
        "task_id": task_id,
        "mode": mode,
        "ok": ok,
    }
    append_jsonl(ledger_path, ledger_payload)

    processed_path = processed_dir / task_path.name
    shutil.move(str(task_path), str(processed_path))


def watch_loop(root: Path, interval: float) -> None:
    inbox_dir = root / "observability" / "bridge" / "inbox" / MODULE_NAME
    ensure_dir(inbox_dir)
    while True:
        tasks = sorted(inbox_dir.glob("*.json"))
        for task_path in tasks:
            try:
                process_task(task_path, root)
            except Exception as exc:  # noqa: BLE001 - capture any task failure
                error_payload = {
                    "ts": utc_ts(),
                    "module": MODULE_NAME,
                    "event": "task_failed",
                    "task": task_path.name,
                    "error": sanitize_error(exc),
                }
                ledger_path = root / "observability" / "stl" / "ledger" / "global_beacon.jsonl"
                append_jsonl(ledger_path, error_payload)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser operator worker")
    parser.add_argument("--root", default=None, help="Repo root path")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval")
    args = parser.parse_args()

    if args.root:
        root = Path(args.root).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2]

    watch_loop(root, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
