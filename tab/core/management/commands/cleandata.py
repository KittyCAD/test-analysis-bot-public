from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

import log

from tab.api.constants import TESTS_CACHE_KEY
from tab.projects.models import Project, Result, Run, Test
from tab.releases.constants import RESULTS_TIMEOUT
from tab.releases.enums import Type
from tab.releases.models import Environment, Release

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
        log.info(f"Started job at {start.strftime('%Y-%m-%d %H:%M:%S')}")
        self.finalize_releases()
        self.delete_stale_environments()
        self.delete_stale_releases()
        for project in Project.objects.all():
            count = 0
            if project.test_stale_threshold:
                count += self.delete_stale_tests(project, dry_run)
            if project.result_stale_threshold:
                count += self.delete_stale_runs(project, dry_run)
                count += self.delete_stale_results(project, dry_run)
            if count:
                project.cleaned_at = timezone.now()
                project.save()
        self.update_bulk_tests()
        delta = timezone.now() - start
        log.info(f"Finished job after {delta.seconds // 60}:{delta.seconds % 60:02d}")

    def delete_stale_tests(self, project: Project, dry_run: bool) -> int:
        log.info(f"Cleaning up stale tests: {project}")

        cutoff = timezone.now() - project.test_stale_threshold
        tests = Test.objects.filter(
            project=project,
            updated_at__lt=cutoff,
        ).order_by()  # remove default ordering for performance
        count = tests.count()

        if dry_run:
            log.warning(f"Would delete {count} tests: {project}")
            return 0

        tests.delete()
        log.info(f"Deleted {count} tests: {project}")
        return count

    def delete_stale_runs(self, project: Project, dry_run: bool) -> int:
        log.info(f"Cleaning up stale runs: {project}")
        cutoff = timezone.now() - (project.result_stale_threshold * 20)
        runs = (
            Run.objects.filter(project=project)
            .filter(setup_started_at__lt=cutoff)
            .order_by()
        )
        count = runs.count()

        if dry_run:
            log.warning(f"Would delete {count} runs: {project}")
            return 0

        runs.delete()
        log.info(f"Deleted {count} runs: {project}")
        return count

    def delete_stale_results(self, project: Project, dry_run: bool) -> int:
        log.info(f"Cleaning up stale results: {project}")

        short_cutoff = timezone.now() - project.result_stale_threshold
        long_cutoff = timezone.now() - (project.result_stale_threshold * 20)
        results = (
            Result.objects.filter(test__project=project)
            .filter(
                # Delete non-default branch results older than the threshold
                (
                    Q(created_at__lt=short_cutoff)
                    & ~Q(branch__in=project.default_branches)
                )
                # Delete default branch results older than the threshold
                | (
                    Q(branch__in=project.default_branches)
                    & Q(created_at__lt=long_cutoff)
                )
            )
            .order_by()  # remove default ordering for performance
        )

        if dry_run:
            count = results.count()
            log.warning(f"Would delete {count} total results: {project}")
            return 0

        deleted = 0
        while True:
            chunk_ids = list(results.values_list("id", flat=True)[:CHUNK_SIZE])
            if not chunk_ids:
                break
            chunk_count = Result.objects.filter(id__in=chunk_ids).delete()[0]
            deleted += chunk_count
            log.info(f"Deleted {chunk_count} chunk results: {project}")

        log.info(f"Deleted {deleted} total results: {project}")
        return deleted

    def update_bulk_tests(self):
        if test_ids := cache.get(TESTS_CACHE_KEY):
            cache.delete(TESTS_CACHE_KEY)
            tests = Test.objects.filter(id__in=test_ids)
            log.info(f"Updating tests: {tests.count()} (multiple projects)")
            for test in tests:
                if test.update():
                    log.info(f"Updated test: {test}")
                test.save()
                for result in (
                    test.results.filter(
                        created_at__gte=timezone.now() - timedelta(hours=1)
                    )
                    .order_by("branch", "-created_at")
                    .distinct("branch")
                ):
                    result.finalize()

    def finalize_releases(self):
        cutoff = timezone.now() - RESULTS_TIMEOUT
        releases = Release.objects.filter(
            created_at__lt=cutoff, finalized_at__isnull=True
        )
        for release in releases:
            release.finalize()

    def delete_stale_environments(self):
        cutoff = timezone.now() - timedelta(weeks=13)
        environments = Environment.objects.filter(
            created_at__lt=cutoff,
            name=Type.REVIEW,
        ).exclude(
            # Preserve example environments with placeholders for identifiers
            url__contains="{"
        )
        for environment in environments:
            environment.delete()

    def delete_stale_releases(self):
        cutoff = timezone.now() - timedelta(weeks=26)
        releases = Release.objects.filter(created_at__lt=cutoff)
        for release in releases:
            release.delete()
