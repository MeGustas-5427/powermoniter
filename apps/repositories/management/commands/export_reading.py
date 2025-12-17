from __future__ import annotations

import gzip
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

from apps.repositories.models import Reading


class Command(BaseCommand):
    help = "Export Reading as a Django JSON fixture (.json.gz) for loaddata."

    def handle(self, *args, **options):
        using = "default"
        chunk_size = 2000
        output_path = Path(settings.BASE_DIR) / "exports" / "reading.json.gz"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        readings = Reading.objects.using(using).all().order_by("pk").iterator(chunk_size=chunk_size)
        fixed_device_id = "019b269d-62b7-7183-9453-6b518bb6704f"

        def rewritten_readings():
            for reading in readings:
                reading.device_id = fixed_device_id
                yield reading

        with gzip.open(output_path, "wt", encoding="utf-8") as fh:
            serializers.serialize(
                "json",
                rewritten_readings(),
                stream=fh,
            )

        self.stdout.write(f"Exported fixture to: {output_path}")
