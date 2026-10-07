"""Read documented Codex usage methods on the signed-in PC; export only numeric summaries.

No inference, scraping, cookies, account IDs or credentials are exported.
Run with --nas truenas_admin@192.168.1.8 to publish over existing SSH access.
"""
import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"server"))
from app.snapshots import ChatGPTUsage  # noqa: E402


def usage_record(usage, limits, now=None):
    now = now or datetime.now(timezone.utc)
    summary = usage.get("summary") or {}
    rate = limits.get("rateLimits") or {}
    primary = rate.get("primary") or {}
    # No free-form provider/account text is forwarded.
    minutes = primary.get("windowDurationMins")
    window = f" {minutes//1440}d" if minutes and minutes % 1440 == 0 else (f" {minutes//60}h" if minutes and minutes % 60 == 0 else "")
    return ChatGPTUsage(source="OpenAI / PC sync", as_of=now, valid_until=now+timedelta(hours=2),
                        lifetime_tokens=summary.get("lifetimeTokens"), peak_daily_tokens=summary.get("peakDailyTokens"),
                        current_streak_days=summary.get("currentStreakDays"), used_percent=primary.get("usedPercent"),
                        window_minutes=minutes, resets_at=datetime.fromtimestamp(primary["resetsAt"], timezone.utc) if primary.get("resetsAt") else None,
                        limit_name=("Codex" if rate.get("limitId") == "codex" else "Account")+window)


def read_usage(executable):
    process = subprocess.Popen([executable, "app-server", "--stdio"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    messages = queue.Queue()
    def reader():
        for line in process.stdout:
            try: messages.put(json.loads(line))
            except ValueError: pass
    threading.Thread(target=reader, daemon=True).start()
    def send(payload):
        process.stdin.write(json.dumps(payload)+"\n")
        process.stdin.flush()
    def request(number, method, params=None):
        send({"id": number, "method": method, **({"params": params} if params is not None else {})})
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            item = messages.get(timeout=max(.1, deadline-time.monotonic()))
            if item.get("id") == number:
                if "error" in item:
                    raise RuntimeError(f"{method} unavailable; check Codex sign-in/version")
                return item["result"]
        raise TimeoutError("Usage request timed out")
    try:
        request(1, "initialize", {"clientInfo": {"name": "kindle_dashboard_usage", "version": "1.0"}})
        send({"method": "initialized", "params": {}})
        limits = request(2, "account/rateLimits/read")
        usage = request(3, "account/usage/read")
        return usage_record(usage, limits)
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".chatgpt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def publish(nas, directory, record):
    # Script and data travel over stdin, never through shell string interpolation.
    script = f'''import os,tempfile
from pathlib import Path
directory=Path({directory!r})
if not directory.is_absolute() or not directory.is_dir(): raise ValueError('Existing NAS data directory required')
fd,name=tempfile.mkstemp(prefix='.chatgpt-',dir=directory)
try:
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        stream.write({record.model_dump_json()!r})
    os.chown(name,10001,10001)
    os.chmod(name,0o640)
    os.replace(name,directory/'chatgpt.json')
finally:
    if os.path.exists(name): os.unlink(name)
print('Usage snapshot published; collector imports it on its next cycle.')
'''
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--", nas, "sudo -n python3 -"],
                            input=script, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("NAS upload failed; check SSH access and data directory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--output", type=Path, default=ROOT/"dist/private/chatgpt.json")
    parser.add_argument("--nas", help="SSH user@host; requires authorized passwordless sudo for atomic data publication")
    parser.add_argument("--nas-directory", default="/mnt/Main/kindle-dashboard/server/data")
    args = parser.parse_args()
    if not args.codex: parser.error("Codex executable not found; pass --codex PATH")
    try:
        record = read_usage(args.codex)
        write_atomic(args.output, record.model_dump_json(indent=2))
        if args.nas: publish(args.nas, args.nas_directory, record)
        print("ChatGPT usage snapshot refreshed." + (" NAS imports it within its next collector cycle." if args.nas else ""))
    except Exception as error:
        print(f"Usage sync failed ({type(error).__name__}); previous snapshots retained.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
