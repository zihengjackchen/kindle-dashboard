"""Export only the original digest text, never its private snapshot/attachments."""
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import tempfile


def export_report(source, output, uid=10001, gid=10001):
    source, output = Path(source), Path(output)
    files = sorted((p for p in source.iterdir() if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", p.name)), reverse=True)
    for path in files:
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError("Source archive too large; previous export retained")
        record = json.loads(raw)
        day = date.fromisoformat(record['local_date']).isoformat()
        created = record['created_at']
        if day != path.stem or datetime.fromisoformat(created.replace('Z', '+00:00')).tzinfo is None:
            raise ValueError("Invalid digest date")
        content = record['content']
        if not isinstance(content, str) or not content.strip() or len(content) > 40000:
            raise ValueError("Invalid digest text")
        # An explicit allowlist keeps account data, source snapshots and webhook
        # receipts in the publisher's private archive.
        result = json.dumps(dict(local_date=day, created_at=created, content=content), ensure_ascii=False).encode('utf-8')
        output.mkdir(parents=True, exist_ok=True)
        if hasattr(os, 'chown'):
            os.chown(output, uid, gid)
        output.chmod(0o750)
        destination = output / path.name
        if destination.exists() and destination.read_bytes() == result:
            return day
        fd, temporary = tempfile.mkstemp(prefix='.report-', dir=output)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(result)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o640)
            if hasattr(os, 'chown'):
                os.chown(temporary, uid, gid)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return day
    raise ValueError("No saved digest; previous export retained")
