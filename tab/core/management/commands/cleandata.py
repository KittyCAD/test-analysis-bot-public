from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from django.utils import timezone

import log

from tab.api.constants import TESTS_CACHE_KEY
from tab.metrics.models import TestHistory
from tab.projects.models import Project, Result, Run, Test
from tab.releases.constants import PLACEHOLDER_CHARACTER, RESULTS_TIMEOUT
from tab.releases.enums import Type
from tab.releases.models import Environment, Release

CHUNK_SIZE = 5000


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
        self.fetch_active_branches()
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
        branch_results = (
            Result.objects.filter(test__project=project)
            .exclude(branch__in=project.default_branches)
            .filter(created_at__lt=short_cutoff)
            .order_by()
        )
        default_results = Result.objects.filter(
            test__project=project,
            branch__in=project.default_branches,
            created_at__lt=long_cutoff,
        ).order_by()

        if dry_run:
            count = branch_results.count() + default_results.count()
            log.warning(f"Would delete {count} total results: {project}")
            return 0

        deleted = self._delete_result_chunks(project, branch_results)
        deleted += self._delete_result_chunks(project, default_results)
        log.info(f"Deleted {deleted} total results: {project}")
        return deleted

    def _delete_result_chunks(self, project: Project, results: QuerySet[Result]) -> int:
        deleted = 0
        while True:
            ids = list(results.values_list("pk", flat=True)[:CHUNK_SIZE])
            if not ids:
                break
            # Clear SET_NULL FKs ourselves so we can skip Django's collector
            Test.objects.filter(last_result_id__in=ids).update(last_result=None)
            TestHistory.objects.filter(result_id__in=ids).update(result=None)
            chunk = Result.objects.filter(pk__in=ids).order_by()
            chunk_count = chunk._raw_delete(chunk.db)
            deleted += chunk_count
            log.info(f"Deleted {chunk_count} chunk results: {project}")
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
                        created_at__gte=timezone.now() - timedelta(hours=1),
                        final=True,
                    )
                    .order_by("commit", "target", "platform", "branch", "-id")
                    .distinct("commit", "target", "platform", "branch")
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
            name=Type.REVIEW, created_at__lt=cutoff
        ).exclude(
            # Preserve example environments with placeholders for identifiers
            url__contains=PLACEHOLDER_CHARACTER,
        )
        for environment in environments:
            environment.delete()

    def delete_stale_releases(self):
        cutoff = timezone.now() - timedelta(weeks=26)
        releases = Release.objects.filter(created_at__lt=cutoff)
        for release in releases:
            release.delete()

    def fetch_active_branches(self):
        for project in Project.objects.all():
            Result.objects.get_active_branches(project)
