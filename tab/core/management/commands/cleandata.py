from django.core.management.base import BaseCommand
from django.utils import timezone

from tab.projects.models import Project, Result, Test

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
            if project.test_stale_threshold:
                self._delete_stale_tests(project, dry_run)
            if project.results_stale_threshold:
                self._delete_stale_results(project, dry_run)

    def _delete_stale_tests(self, project: Project, dry_run: bool):
        self.stdout.write(
            self.style.MIGRATE_LABEL(f"Cleaning up stale tests: {project}")
        )

        cutoff = timezone.now() - project.test_stale_threshold
        tests = Test.objects.filter(
            project=project,
            updated_at__lt=cutoff,
        )
        count = tests.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Would delete {count} tests: {project}")
            )
        else:
            tests.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} tests: {project}"))

    def _delete_stale_results(self, project: Project, dry_run: bool):
        self.stdout.write(
            self.style.MIGRATE_LABEL(f"Cleaning up stale results: {project}")
        )

        cutoff = timezone.now() - project.results_stale_threshold
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
                chunk_ids = results.values_list("id", flat=True)[:CHUNK_SIZE]
                if not chunk_ids:
                    break
                chunk_count = Result.objects.filter(id__in=chunk_ids).delete()[0]
                deleted += chunk_count
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted {deleted}/{count} results: {project}")
                )
