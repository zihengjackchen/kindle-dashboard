"""Generate matching NAS and Kindle configuration without editing tracked files."""
import argparse
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nas-url", required=True, help="For example http://192.168.1.20:8080")
    parser.add_argument("--timezone", default="America/Los_Angeles")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--location", default="")
    parser.add_argument("--unit", choices=["F", "C"], default="F")
    parser.add_argument("--device-id", default="kindle")
    args = parser.parse_args()
    if any(ord(c) < 32 for c in args.nas_url): parser.error("URL must not contain control characters")
    url = urlsplit(args.nas_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
        parser.error("Use a plain HTTP(S) NAS origin without path or credentials")
    import re
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", args.device_id): parser.error("Invalid device ID")
    ZoneInfo(args.timezone)
    if (args.latitude is None) != (args.longitude is None): parser.error("Supply both coordinates")
    if args.latitude is not None and not (-90 <= args.latitude <= 90 and -180 <= args.longitude <= 180): parser.error("Invalid coordinates")
    if any(c in args.location for c in '\n\r\x00'): parser.error("Location must fit on one line")
    env_path = ROOT / "server/.env"
    if env_path.exists(): parser.error("server/.env already exists; preserve it and configure manually (docs/setup.md)")
    token = secrets.token_hex(24)
    env = (ROOT / "server/.env.example").read_text(encoding="utf-8")
    values = {"API_TOKEN": token, "DASHBOARD_TIMEZONE": args.timezone,
              "WEATHER_LATITUDE": "" if args.latitude is None else str(args.latitude),
              "WEATHER_LONGITUDE": "" if args.longitude is None else str(args.longitude),
              "WEATHER_LOCATION": args.location, "WEATHER_UNIT": args.unit}
    # Compose dotenv single quotes preserve spaces, $, # and backslashes.
    def quote(value): return "'" + value.replace("'", "\\'") + "'"
    env = "\n".join(line.split("=", 1)[0]+"="+quote(values[line.split("=",1)[0]])
                    if line.split("=",1)[0] in values else line for line in env.splitlines())+"\n"
    os.umask(0o077)
    env_path.write_text(env, encoding="utf-8")
    folder = ROOT / "dist/private"
    folder.mkdir(parents=True, exist_ok=True)
    config = folder / "config.local.sh"
    config.write_text("#!/bin/sh\n" + "\n".join(f"{key}={shlex.quote(value)}" for key, value in
                      {"DASHBOARD_URL": args.nas_url.rstrip('/')+"/dashboard.png", "API_TOKEN": token,
                       "DEVICE_ID": args.device_id}.items())+"\n", encoding="utf-8", newline="\n")
    subprocess.run([sys.executable, str(ROOT / "scripts/package-client.py"), "--private-config", str(config),
                    "--output", str(folder / "kindle-dashboard-configured.zip")], check=True)
    print("Created server/.env and a PRIVATE configured Kindle ZIP. Do not publish these files.")
    print("NAS: cd server; docker compose up -d --build. Optional live sources: --profile live.")


if __name__ == "__main__": main()
