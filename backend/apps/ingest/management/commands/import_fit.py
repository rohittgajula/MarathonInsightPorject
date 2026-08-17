from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.athletes.models import Athlete
from apps.ingest.models import RawFitFile
from apps.ingest.services import ingest_fit


class Command(BaseCommand):
    help = "Import one or more .fit files for an athlete."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+")
        parser.add_argument("--athlete", type=int, required=True)

    def handle(self, *args, **opts):
        try:
            athlete = Athlete.objects.get(pk=opts["athlete"])
        except Athlete.DoesNotExist:
            raise CommandError(f"No athlete with id {opts['athlete']}")

        for raw_path in opts["paths"]:
            path = Path(raw_path)
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"missing: {path}"))
                continue

            data = path.read_bytes()
            digest = RawFitFile.hash_bytes(data)
            if RawFitFile.objects.filter(athlete=athlete, sha256=digest).exists():
                self.stdout.write(f"skip (already imported): {path.name}")
                continue

            with path.open("rb") as handle:
                raw = RawFitFile.objects.create(
                    athlete=athlete,
                    file=File(handle, name=path.name),
                    original_name=path.name,
                    sha256=digest,
                    size_bytes=len(data),
                )
            activity = ingest_fit(raw)
            metrics = activity.metrics
            self.stdout.write(
                self.style.SUCCESS(
                    f"{path.name} -> activity {activity.pk}: "
                    f"{activity.total_distance_m/1000:.2f} km, "
                    f"{metrics.run_block_count} run blocks, "
                    f"longest {metrics.longest_run_s:.0f}s"
                )
            )
