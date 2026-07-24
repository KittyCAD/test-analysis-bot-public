from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

import pytest

from tab.api.constants import TESTS_CACHE_KEY
from tab.core.management.commands.cleandata import Command
from tab.projects.enums import Status, Target
from tab.projects.models import Project, Result


@pytest.mark.django_db
def describe_delete_stale_results(expect):
    def it_deletes_stale_results_and_keeps_recent_ones():
        project = Project.objects.create(
            repository="https://github.com/foo/bar",
            result_stale_threshold=timedelta(days=7),
            default_branches=["main"],
        )
        test = project.tests.create(name="my-test")
        now = timezone.now()

        stale_feature = Result.objects.create(
            test=test, status=Status.PASSED, branch="feature", commit="a1"
        )
        recent_feature = Result.objects.create(
            test=test, status=Status.PASSED, branch="feature", commit="a2"
        )
        stale_default = Result.objects.create(
            test=test, status=Status.PASSED, branch="main", commit="b1"
        )
        old_default = Result.objects.create(
            test=test, status=Status.PASSED, branch="main", commit="b2"
        )
        Result.objects.filter(pk=stale_feature.pk).update(
            created_at=now - timedelta(days=8)
        )
        Result.objects.filter(pk=recent_feature.pk).update(
            created_at=now - timedelta(days=1)
        )
        # Default branches use a 20x longer threshold
        Result.objects.filter(pk=stale_default.pk).update(
            created_at=now - timedelta(days=8)
        )
        Result.objects.filter(pk=old_default.pk).update(
            created_at=now - timedelta(days=141)
        )

        deleted = Command().delete_stale_results(project, dry_run=False)

        expect(deleted) == 2
        expect(set(test.results.values_list("commit", flat=True))) == {"a2", "b1"}

    def it_does_nothing_on_dry_run():
        project = Project.objects.create(
            repository="https://github.com/foo/baz",
            result_stale_threshold=timedelta(days=7),
        )
        test = project.tests.create(name="my-test")
        result = Result.objects.create(
            test=test, status=Status.PASSED, branch="feature", commit="a1"
        )
        Result.objects.filter(pk=result.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )

        deleted = Command().delete_stale_results(project, dry_run=True)

        expect(deleted) == 0
        expect(test.results.count()) == 1


@pytest.mark.django_db
def describe_update_bulk_tests(expect):
    def it_finalizes_recent_bulk_created_duplicates():
        project = Project.objects.create(repository="https://github.com/foo/bar")
        test = project.tests.create(name="my-test")
        now = timezone.now()
        Result.objects.bulk_create(
            [
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    final=True,
                    created_at=now,
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    final=True,
                    created_at=now,
                ),
            ]
        )
        cache.set(TESTS_CACHE_KEY, {test.id})

        Command().update_bulk_tests()

        expect(test.results.filter(final=True).count()) == 1

    def it_finalizes_each_target_separately():
        project = Project.objects.create(repository="https://github.com/foo/bar")
        test = project.tests.create(name="my-test")
        now = timezone.now()
        Result.objects.bulk_create(
            [
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    target=Target.WEB.value,
                    final=True,
                    created_at=now,
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    target=Target.WEB.value,
                    final=True,
                    created_at=now,
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    target=Target.DESKTOP.value,
                    final=True,
                    created_at=now,
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    target=Target.DESKTOP.value,
                    final=True,
                    created_at=now,
                ),
            ]
        )
        cache.set(TESTS_CACHE_KEY, {test.id})

        Command().update_bulk_tests()

        expect(test.results.filter(final=True).count()) == 2

    def it_ignores_non_final_results_when_selecting():
        project = Project.objects.create(repository="https://github.com/foo/bar")
        test = project.tests.create(name="my-test")
        now = timezone.now()
        Result.objects.bulk_create(
            [
                Result(
                    test=test,
                    status=Status.FAILED,
                    branch="main",
                    commit="a1",
                    final=False,
                    created_at=now,
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    final=True,
                    created_at=now - timedelta(seconds=1),
                ),
                Result(
                    test=test,
                    status=Status.PASSED,
                    branch="main",
                    commit="a1",
                    final=True,
                    created_at=now - timedelta(seconds=1),
                ),
            ]
        )
        cache.set(TESTS_CACHE_KEY, {test.id})

        Command().update_bulk_tests()

        expect(test.results.filter(final=True).count()) == 1
