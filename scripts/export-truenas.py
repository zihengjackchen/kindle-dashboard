"""Run on the TrueNAS host: export a small, read-only health snapshot for the NAS collector.

Uses built-in Python and midclt. Does not mount a management socket in Docker.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def call(method):
    result = subprocess.run(["midclt", "call", method], capture_output=True, text=True, timeout=15, check=True)
    return json.loads(result.stdout)


def cpu_sample():
    fields = [int(v) for v in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
    return sum(fields), fields[3]+fields[4]


def export(pool_name, call_api=call):
    info, pools, alerts = call_api("system.info"), call_api("pool.query"), call_api("alert.list")
    pool = next(p for p in pools if p["name"] == pool_name)
    if not isinstance(alerts, list): raise ValueError("Unexpected alerts response")
    health = pool.get("status", "UNKNOWN")
    if health not in ("ONLINE", "DEGRADED", "FAULTED"): health = "UNKNOWN"
    size, allocated = pool.get("size"), pool.get("allocated")
    used = None
    if size is not None and allocated is not None:
        size, allocated = int(size), int(allocated)
        if size <= 0 or not 0 <= allocated <= size: raise ValueError("Invalid pool capacity")
        used = 100*allocated/size
    mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    before = cpu_sample()
    time.sleep(1)
    after = cpu_sample()
    total, idle = after[0]-before[0], after[1]-before[1]
    cpu = max(0, min(100, 100*(1-idle/total))) if total > 0 else None
    now = datetime.now(timezone.utc)
    return dict(source="TrueNAS local export", as_of=now.isoformat(), valid_until=(now+timedelta(minutes=30)).isoformat(),
                name=pool_name[:40], version=str(info.get("version", "unknown"))[:40], pool_health=health,
                used_percent=used, cpu_percent=cpu,
                memory_percent=100*(1-mem['MemAvailable']/mem['MemTotal']),
                alerts=sum(not a.get("dismissed", False) for a in alerts), uptime=str(info.get("uptime", "unknown"))[:40])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try: data = export(args.pool)
    except (OSError, ValueError, TypeError, KeyError, StopIteration, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Export failed ({type(exc).__name__}); previous snapshot retained. Check version and pool name.\n")
    fd, name = tempfile.mkstemp(prefix="nas-", suffix=".tmp", dir=args.output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream: json.dump(data, stream)
        os.chmod(name, 0o644)  # contains only selected health fields, no credentials
        os.replace(name, args.output)
    finally:
        if os.path.exists(name): os.unlink(name)
    print("NAS snapshot written")


if __name__ == "__main__": main()
