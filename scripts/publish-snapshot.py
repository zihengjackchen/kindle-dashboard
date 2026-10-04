"""Validate a full weather/market/NAS snapshot, then atomically publish it."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from app.snapshots import Snapshot  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("input", type=Path)
parser.add_argument("--output", type=Path, default=ROOT / "server/data/snapshot.json")
args = parser.parse_args()
with args.input.open("rb") as stream:
    raw = stream.read(262145)
if len(raw) > 262144:
    parser.error("Snapshot exceeds 256 KiB")
snapshot = Snapshot.model_validate_json(raw)
args.output.parent.mkdir(parents=True, exist_ok=True)
temporary = None
try:
    with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(snapshot.model_dump_json().encode())
        stream.flush()
        os.fsync(stream.fileno())
    # Current schema is public weather/quotes/health, never credentials/holdings.
    temporary.chmod(0o644)
    os.replace(temporary, args.output)
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)
print(f"Published validated snapshot: {args.output}")
