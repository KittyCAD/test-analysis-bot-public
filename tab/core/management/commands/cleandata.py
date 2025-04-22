from django.core.management.base import BaseCommand
from django.utils import timezone

from tab.projects.models import Project, Result

CHUNK_SIZE = 1000


class Command(BaseCommand):
    help = "Delete inactive and stale test results"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        for project in Project.objects.all():
            if project.branch_inactive_threshold:
                self._delete_stale_results(project, dry_run)

    def _delete_stale_results(self, project: Project, dry_run: bool):
        self.stdout.write(
            self.style.MIGRATE_LABEL(f"Cleaning up stale results: {project}")
        )

        cutoff = timezone.now() - project.branch_inactive_threshold
        results = Result.objects.filter(
            test__project=project,
            created_at__lt=cutoff,
        ).exclude(branch__in=project.default_branches)
        count = results.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Would delete {count} results: {project}")
            )
        else:
            deleted = 0
            while True:
                chunk = results[:CHUNK_SIZE]
                if not chunk.exists():
                    break
                chunk_count = chunk.count()
                chunk.delete()
                deleted += chunk_count
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted {deleted}/{count} results: {project}")
                )
