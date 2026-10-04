"""Bounded contact history; device-reported success is from the previous fetch."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class ContactStore:
    def __init__(self, path=""):
        self.path = Path(path) if path else None
        self.lock = Lock()
        self.devices = {}
        if self.path:
            try:
                with self.path.open("rb") as stream:
                    raw = stream.read(65537)
                records = json.loads(raw) if len(raw) <= 65536 else {}
                if isinstance(records, dict):
                    self.devices = dict(list(records.items())[-32:])
            except (OSError, ValueError):
                pass

    def contact(self, data):
        if data.device_id is None:
            return
        record = data.model_dump(exclude_none=True)
        record["last_seen"] = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.devices.pop(data.device_id, None)
            self.devices[data.device_id] = record
            while len(self.devices) > 32:
                del self.devices[next(iter(self.devices))]
            if self.path:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temp = self.path.with_suffix(".tmp")
                    temp.write_text(json.dumps(self.devices), encoding="utf-8")
                    os.replace(temp, self.path)
                except OSError:
                    logging.getLogger("dashboard").warning("Contact history persistence unavailable")

    def snapshot(self):
        with self.lock:
            return dict(self.devices)
