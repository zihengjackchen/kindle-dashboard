"""Read usage via the NAS's signed-in Codex CLI. Python standard library only.

No inference requests, thread reads, login changes, cookies or credentials are
exported. Run as the NAS user who already signed in, with that user's normal HOME.
Only this script's short-lived app-server process is terminated on completion.
"""
import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def number(value, maximum=9007199254740991, integer=True):
    if value is None:
        return None
    if type(value) not in ((int,) if integer else (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError("Invalid usage metric")
    return value


def usage_record(usage, limits, now=None):
    """Allowlist only. In particular, omit threadUsage and accountId entirely."""
    now = now or datetime.now(timezone.utc)
    summary = usage.get("summary") or {}
    rate = (limits.get("rateLimitsByLimitId") or {}).get("codex") or limits.get("rateLimits") or {}

    def window(value):
        if not value or value.get("usedPercent") is None:
            return None
        minutes = number(value.get("windowDurationMins"), 525600)
        if minutes == 0:
            raise ValueError("Invalid usage window")
        reset = number(value.get("resetsAt"), 253402300799)
        return dict(used_percent=number(value["usedPercent"], 100, integer=False), window_minutes=minutes,
                    resets_at=datetime.fromtimestamp(reset, timezone.utc).isoformat() if reset is not None else None)

    buckets = usage.get("dailyUsageBuckets") or []
    if not isinstance(buckets, list) or len(buckets) > 10000:
        raise ValueError("Invalid daily usage buckets")
    # Use the provider's date. Do not relabel it as the NAS's local 'today'.
    days = [(date.fromisoformat(b["startDate"]), number(b.get("tokens"))) for b in buckets]
    latest = max(days, key=lambda item: item[0]) if days else None
    return dict(source="Codex account", as_of=now.isoformat(), valid_until=(now+timedelta(hours=2)).isoformat(),
                limit_name="Codex" if rate.get("limitId") == "codex" else "Account",
                primary=window(rate.get("primary")), secondary=window(rate.get("secondary")),
                lifetime_tokens=number(summary.get("lifetimeTokens")), peak_daily_tokens=number(summary.get("peakDailyTokens")),
                current_streak_days=number(summary.get("currentStreakDays"), 100000),
                longest_streak_days=number(summary.get("longestStreakDays"), 100000),
                longest_running_turn_seconds=number(summary.get("longestRunningTurnSec"), 31536000),
                latest_day=latest[0].isoformat() if latest else None, latest_day_tokens=latest[1] if latest else None)


def read_usage(executable, timeout=45):
    process = subprocess.Popen([executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    messages = queue.Queue(maxsize=16)

    def reader():
        try:
            while True:
                line = process.stdout.readline(16 * 1024 * 1024 + 1)
                if not line or len(line) > 16 * 1024 * 1024:
                    break
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and "id" in item:
                        messages.put_nowait(item)
                except (ValueError, queue.Full):
                    pass
        finally:
            try:
                messages.put_nowait(None)
            except queue.Full:
                pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    deadline = time.monotonic()+timeout

    def send(payload):
        process.stdin.write(json.dumps(payload)+"\n")
        process.stdin.flush()

    def request(identifier, method, params=None):
        send(dict(id=identifier, method=method, **({"params": params} if params is not None else {})))
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Usage read timed out")
            try:
                item = messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("Usage read timed out") from None
            if item is None:
                raise RuntimeError("Codex app-server closed before returning usage")
            if item.get("id") == identifier:
                if "error" in item or not isinstance(item.get("result"), dict):
                    # Provider errors can contain private account information.
                    raise RuntimeError("Usage method unavailable; check NAS Codex version and sign-in")
                return item["result"]

    try:
        request(1, "initialize", {"clientInfo": {"name": "kindle_dashboard_usage", "version": "2.0"}})
        send({"method": "initialized", "params": {}})
        limits = request(2, "account/rateLimits/read")
        usage = request(3, "account/usage/read")
        return usage_record(usage, limits)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        reader_thread.join(timeout=2)
        process.stdin.close()
        process.stdout.close()


def write_atomic(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(record, allow_nan=False, separators=(",", ":")).encode()
    if len(content) > 16384:
        raise ValueError("Filtered snapshot is too large")
    fd, name = tempfile.mkstemp(prefix=".usage-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o640)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=shutil.which("codex"), help="Absolute path to the signed-in NAS user's Codex executable")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent/"server/data/codex/usage.json")
    args = parser.parse_args()
    if not args.codex:
        parser.error("Codex not found; pass --codex /absolute/path/to/codex")
    try:
        record = read_usage(args.codex)
        write_atomic(args.output, record)
    except Exception as error:
        print(f"Usage sync failed ({type(error).__name__}); previous snapshot retained. Check NAS Codex sign-in/version.", file=sys.stderr)
        return 1
    print("Usage snapshot refreshed; no model inference was requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
