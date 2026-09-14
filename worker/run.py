#!/usr/bin/env python3
"""
Generic page-fetch runner.

This program contains no site knowledge of its own. It asks the configured
API for a work plan, runs the program that plan hands back, and reports the
result. Nothing about what is fetched, how it is paced or what is kept lives
in this repository.

Environment:
  WORKER_API_BASE   https://host              (repository secret)
  WORKER_TOKEN      bearer token for the API  (repository secret)
  TASK              opaque task id, e.g. task-a
  LIMIT             optional per-run size hint
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

API = os.environ["WORKER_API_BASE"].rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
TASK = os.environ.get("TASK", "").strip()
LIMIT = os.environ.get("LIMIT", "").strip()

HEADERS = {
    "authorization": f"Bearer {TOKEN}",
    "content-type": "application/json",
    "accept": "application/json",
    # Some edges refuse the default urllib agent outright.
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
}

WORK_DIR = "/tmp/worker"
LOG_PATH = os.path.join(WORK_DIR, "run.log")


def call(method: str, path: str, payload=None):
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=HEADERS,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read().decode()
    return json.loads(body) if body else {}


def report(job_name: str, ok: bool, note: str, duration_ms: int):
    """Send the outcome home. Detail stays there, not in the public log."""
    try:
        call(
            "POST",
            "/api/public/hooks/job-log",
            {
                "jobName": job_name,
                "ok": ok,
                "note": note[:4000],
                "durationMs": duration_ms,
            },
        )
    except Exception as exc:  # noqa: BLE001 - reporting must never fail the run
        print(f"report failed: {type(exc).__name__}", file=sys.stderr)


def main() -> int:
    if not TASK:
        print("no task given", file=sys.stderr)
        return 2

    started = time.time()
    plan = call("GET", f"/api/public/hooks/worker-plan?task={TASK}&limit={LIMIT}")
    job_name = plan.get("jobName") or TASK

    os.makedirs(WORK_DIR, exist_ok=True)
    entry = os.path.join(WORK_DIR, plan.get("entry") or "main.py")
    with open(entry, "w", encoding="utf-8") as handle:
        handle.write(plan["module"])

    requirements = plan.get("requirements") or []
    if requirements:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", *requirements],
            check=True,
        )
    if plan.get("playwright"):
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True,
        )

    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (plan.get("env") or {}).items()})

    command = [sys.executable, entry, *[str(a) for a in plan.get("args") or []]]
    if plan.get("xvfb"):
        command = ["xvfb-run", "-a", *command]

    # The child's output can name the sites it visits, so it is written to a
    # file and posted back over the authenticated connection instead of being
    # printed into this repository's public run log.
    print(f"running {TASK}")
    with open(LOG_PATH, "w", encoding="utf-8") as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)

    duration_ms = int((time.time() - started) * 1000)
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as log:
            tail = log.read()[-4000:]
    except OSError:
        tail = ""

    ok = result.returncode == 0
    report(job_name, ok, f"exit {result.returncode}\n{tail}", duration_ms)
    print(f"{TASK} finished: exit {result.returncode} in {duration_ms // 1000}s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
