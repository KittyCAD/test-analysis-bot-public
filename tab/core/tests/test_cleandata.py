from datetime import datetime, timedelta
from unittest.mock import ANY, PropertyMock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

import pytest

from tab.api.constants import TESTS_CACHE_KEY
from tab.core.management.commands.cleandata import Command, is_weekend
from tab.projects.enums import Status, Target
from tab.projects.models import Project, Result, Test

ET = ZoneInfo("America/New_York")


def _command_with_budget() -> Command:
    command = Command()
    command._time_budget_deadline = timezone.now() + timedelta(hours=1)
    command._time_budget_warned = False
    return command


def describe_is_weekend(expect):
    def it_is_false_on_weekdays():
        expect(is_weekend(datetime(2026, 8, 7, 10, tzinfo=ET))) is False  # Friday

    def it_is_true_on_saturday():
        expect(is_weekend(datetime(2026, 8, 8, 10, tzinfo=ET))) is True

    def it_is_true_on_sunday():
        expect(is_weekend(datetime(2026, 8, 9, 10, tzinfo=ET))) is True


@pytest.mark.django_db
def describe_handle_weekend_cleanup(expect):
    def it_skips_stale_cleanup_on_weekdays(mocker):
        mocker.patch(
            "tab.core.management.commands.cleandata.is_weekend",
            return_value=False,
        )
        delete_stale = mocker.patch.object(Command, "delete_stale_data")
        mocker.patch.object(Command, "finalize_releases")
        mocker.patch.object(Command, "fetch_active_branches")
        mocker.patch.object(Command, "update_bulk_tests")

        Command().handle(dry_run=False, force=False)

        expect(delete_stale.called) is False

    def it_runs_stale_cleanup_on_weekends(mocker):
        mocker.patch(
            "tab.core.management.commands.cleandata.is_weekend",
            return_value=True,
        )
        delete_stale = mocker.patch.object(Command, "delete_stale_data")
        mocker.patch.object(Command, "finalize_releases")
        mocker.patch.object(Command, "fetch_active_branches")
        mocker.patch.object(Command, "update_bulk_tests")

        Command().handle(dry_run=False, force=False)

        delete_stale.assert_called_once_with(False, ANY)

    def it_runs_stale_cleanup_with_force_on_weekdays(mocker):
        mocker.patch(
            "tab.core.management.commands.cleandata.is_weekend",
            return_value=False,
        )
        delete_stale = mocker.patch.object(Command, "delete_stale_data")
        mocker.patch.object(Command, "finalize_releases")
        mocker.patch.object(Command, "fetch_active_branches")
        mocker.patch.object(Command, "update_bulk_tests")

        Command().handle(dry_run=False, force=True)

        delete_stale.assert_called_once_with(False, ANY)


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
        # Default branches use a 5x longer threshold
        Result.objects.filter(pk=stale_default.pk).update(
            created_at=now - timedelta(days=8)
        )
        Result.objects.filter(pk=old_default.pk).update(
            created_at=now - timedelta(days=36)
        )
        # Point last_result at a row that will be deleted (bypass Test.save)
        Test.objects.filter(pk=test.pk).update(last_result=stale_feature)

        deleted = _command_with_budget().delete_stale_results(project, dry_run=False)

        expect(deleted) == 2
        expect(set(test.results.values_list("commit", flat=True))) == {"a2", "b1"}
        test.refresh_from_db()
        expect(test.last_result_id) == None

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

        deleted = _command_with_budget().delete_stale_results(project, dry_run=True)

        expect(deleted) == 0
        expect(test.results.count()) == 1

    def it_stops_when_time_budget_is_exhausted(mocker):
        project = Project.objects.create(
            repository="https://github.com/foo/budget",
            result_stale_threshold=timedelta(days=7),
        )
        test = project.tests.create(name="my-test")
        now = timezone.now()
        for i in range(3):
            result = Result.objects.create(
                test=test, status=Status.PASSED, branch="feature", commit=f"c{i}"
            )
            Result.objects.filter(pk=result.pk).update(
                created_at=now - timedelta(days=8)
            )

        mocker.patch("tab.core.management.commands.cleandata.CHUNK_SIZE", 1)
        command = Command()
        mocker.patch.object(
            type(command),
            "time_budget_remaining",
            new_callable=PropertyMock,
            side_effect=[True, False],
        )

        deleted = command.delete_stale_results(project, dry_run=False)

        expect(deleted) == 1
        expect(test.results.count()) == 2


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
