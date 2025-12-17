from __future__ import annotations

import gzip
import json
from collections import deque
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.repositories.models import Reading, Device


def iter_json_array(stream, *, chunk_size: int = 1024 * 1024):
    decoder = json.JSONDecoder()
    buf = ""
    idx = 0

    def read_more() -> bool:
        nonlocal buf
        chunk = stream.read(chunk_size)
        if not chunk:
            return False
        buf += chunk
        return True

    def ensure_data() -> None:
        nonlocal buf, idx
        if idx > 1024 * 1024:
            buf = buf[idx:]
            idx = 0

    while True:
        while idx < len(buf) and buf[idx].isspace():
            idx += 1
        if idx < len(buf):
            break
        if not read_more():
            raise ValueError("Unexpected EOF while looking for '['")
        ensure_data()

    if buf[idx] != "[":
        raise ValueError("Invalid JSON: expected '['")
    idx += 1

    while True:
        while True:
            while idx < len(buf) and buf[idx].isspace():
                idx += 1
            if idx < len(buf):
                break
            if not read_more():
                raise ValueError("Unexpected EOF inside array")
            ensure_data()

        if buf[idx] == "]":
            return

        while True:
            try:
                obj, end = decoder.raw_decode(buf, idx)
                idx = end
                yield obj
                break
            except json.JSONDecodeError:
                if not read_more():
                    raise
                ensure_data()

        while True:
            while idx < len(buf) and buf[idx].isspace():
                idx += 1
            if idx < len(buf):
                break
            if not read_more():
                raise ValueError("Unexpected EOF after item")
            ensure_data()

        if buf[idx] == ",":
            idx += 1
            ensure_data()
            continue
        if buf[idx] == "]":
            return
        raise ValueError(f"Invalid JSON: expected ',' or ']', got {buf[idx]!r}")


class Command(BaseCommand):
    help = "Print first 10 and last 10 objects from exports/reading.json.gz."
    requires_system_checks = []

    def handle(self, *args, **options):
        path = Path(settings.BASE_DIR) / "exports" / "reading.json.gz"
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        with gzip.open(path, "rt", encoding="utf-8") as fh:
            device = Device.objects.first()
            a = []
            for obj in iter_json_array(fh):
                data = obj.get("fields")
                data["device"] = device
                a.append(Reading(**data))

            Reading.objects.bulk_create(a)