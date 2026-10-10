"""Prepare NiLuJe's prebuilt Kindle HTTP helper; never run the USBNet installer."""
import argparse
import hashlib
import io
from pathlib import Path
import tarfile
from urllib.request import urlopen

URL = "https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/Touch/kindle-usbnet-0.22.N-r19297.tar.xz"
ARCHIVE_SHA256 = "cf971557d42cc0a6d7699f1c743108c681fa41e3d67ee5802a91932d130d4032"
BINARY_SHA256 = "56de028abc88a751850c139ec392ec945e0d4bb2d115525c52fcc13d95449b9f"
MEMBER = "USBNetwork/src/usbnet/bin/busybox"


def prepare(data: bytes, destination: Path):
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Upstream archive checksum mismatch; no files installed")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as archive:
        member = archive.getmember(MEMBER)
        if not member.isfile() or member.size > 2_000_000:
            raise ValueError("Unexpected BusyBox archive entry")
        binary = archive.extractfile(member).read()
        readme = archive.extractfile("USBNetwork/README").read()
    if hashlib.sha256(binary).hexdigest() != BINARY_SHA256:
        raise ValueError("BusyBox checksum mismatch; no files installed")
    # ELF32, little endian, ARM; this build targets legacy K5 Kindles.
    if binary[:7] != b"\x7fELF\x01\x01\x01" or binary[18:20] != b"\x28\x00":
        raise ValueError("Unexpected executable architecture")
    destination.mkdir(parents=True, exist_ok=True)
    pending = destination / "busybox.tmp"
    pending.write_bytes(binary)
    pending.chmod(0o755)
    pending.replace(destination / "busybox")
    (destination / "upstream-README.txt").write_bytes(readme)
    (destination / "PROVENANCE.txt").write_text(
        "BusyBox 1.34.1, GPL-2.0; prebuilt by NiLuJe for legacy K5 Kindles.\n"
        "Upstream release: https://www.mobileread.com/forums/showthread.php?t=225030\n"
        f"Archive: {URL}\nArchive SHA256: {ARCHIVE_SHA256}\n"
        f"Member: {MEMBER}\nBinary SHA256: {BINARY_SHA256}\n"
        "Only this helper was extracted. USBNetwork was not installed.\n"
        "Keep this private local installation out of public release archives.\n"
        "See upstream-README.txt for upstream credits and license information.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a previously downloaded pinned archive")
    parser.add_argument("--destination", type=Path, default=Path("dist/private/httpd-helper"))
    args = parser.parse_args()
    if args.archive:
        data = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=90) as response:
            data = response.read(64 * 1024 * 1024 + 1)
    prepare(data, args.destination)
    print(f"Verified ARM HTTP helper prepared in {args.destination}")
