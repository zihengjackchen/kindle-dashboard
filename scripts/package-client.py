"""Build a USB-installable ZIP without caches, reports or state."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import argparse

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "kindle-client"
extension = source / "extensions" / "dashboard"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--private-config", type=Path, help="Explicitly include a private config.local.sh")
parser.add_argument("--output", type=Path, default=ROOT / "dist" / "kindle-dashboard-client.zip")
args = parser.parse_args()
destination = args.output
destination.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
    files = sorted(p for p in extension.glob("*.sh") if p.name != "config.local.sh") + [extension / "config.xml", extension / "menu.json"]
    files += sorted((extension / "lib").glob("*.sh")) + sorted((extension / "lib").glob("*.awk"))
    files += sorted((extension / "app").glob("*")) + sorted((source / "documents").glob("*.sh"))
    for path in files:
        entry = ZipInfo(path.relative_to(source).as_posix())
        entry.create_system = 3
        entry.external_attr = (0o100755 if path.suffix in (".sh", ".cgi") else 0o100644) << 16
        entry.compress_type = ZIP_DEFLATED
        archive.writestr(entry, path.read_bytes().replace(b"\r\n", b"\n"))
    for folder in ("cache", "state", "logs"):
        archive.writestr(f"extensions/dashboard/{folder}/", b"")
    if args.private_config:
        archive.writestr("extensions/dashboard/config.local.sh", args.private_config.read_bytes().replace(b"\r\n", b"\n"))
print(destination)
