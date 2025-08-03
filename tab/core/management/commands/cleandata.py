from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from tab.api.constants import TESTS_TO_UPDATE_CACHE_KEY
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
        start = timezone.now()
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Started job at {start.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        for project in Project.objects.all():
            count = 0
            if project.test_stale_threshold:
                count += self._delete_stale_tests(project, dry_run)
            if project.result_stale_threshold:
                count += self._delete_stale_results(project, dry_run)
            if count:
                project.cleaned_at = timezone.now()
                project.save()
        self._update_tests()
        delta = timezone.now() - start
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Finished job after {delta.seconds // 60}:{delta.seconds % 60:02d}"
            )
        )

    def _delete_stale_tests(self, project: Project, dry_run: bool) -> int:
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
            return 0

        tests.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} tests: {project}"))
        return count

    def _delete_stale_results(self, project: Project, dry_run: bool) -> int:
        self.stdout.write(
            self.style.MIGRATE_LABEL(f"Cleaning up stale results: {project}")
        )

        cutoff = timezone.now() - project.result_stale_threshold
        results = Result.objects.filter(
            test__project=project,
            created_at__lt=cutoff,
        ).exclude(branch__in=project.default_branches)
        count = results.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Would delete {count} results: {project}")
            )
            return 0

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
        return deleted

    def _update_tests(self):
        if test_ids := cache.get(TESTS_TO_UPDATE_CACHE_KEY):
            cache.delete(TESTS_TO_UPDATE_CACHE_KEY)
            tests = Test.objects.filter(id__in=test_ids)
            self.stdout.write(
                self.style.MIGRATE_LABEL(f"Processing {tests.count()} tests")
            )
            for test in tests:
                if test.update():
                    self.stdout.write(self.style.SUCCESS(f"Updated test: {test}"))
                test.save()
                for result in (
                    test.results.filter(
                        created_at__gte=timezone.now() - timedelta(hours=1)
                    )
                    .order_by("branch", "-created_at")
                    .distinct("branch")
                ):
                    result.finalize()
