from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

import pytest

from ..constants import PENDING_THRESHOLD
from ..models import Project, Result, Run, Status, Suite, Test


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


def describe_result_manager(expect, project: Project):
    def describe_get_active_branches(expect):
        @pytest.mark.django_db
        def it_returns_distinct_branches_ordered_by_name():
            test = Test.objects.create(project=project, name="t")
            Result.objects.create(
                test=test,
                branch="main",
                commit="a",
                status=Status.PASSED,
                final=True,
            )
            Result.objects.create(
                test=test,
                branch="feature",
                commit="b",
                status=Status.PASSED,
                final=True,
            )

            branches = Result.objects.get_active_branches(project)

            expect(branches) == ["feature", "main"]

        @pytest.mark.django_db
        def it_excludes_branches_older_than_branch_inactive_threshold():
            project.branch_inactive_threshold = timedelta(days=1)
            project.save()
            test = Test.objects.create(project=project, name="t")
            old = timezone.now() - timedelta(days=10)
            Result.objects.create(
                test=test,
                branch="stale",
                commit="a",
                status=Status.PASSED,
                final=True,
            )
            Result.objects.filter(branch="stale").update(created_at=old)
            Result.objects.create(
                test=test,
                branch="fresh",
                commit="b",
                status=Status.PASSED,
                final=True,
            )

            branches = Result.objects.get_active_branches(project)

            expect(branches) == ["fresh"]

    def describe_get_health(expect):
        @pytest.mark.django_db
        def it_returns_health_metrics():
            test1 = Test.objects.create(project=project, name="test1")
            Result.objects.create(
                test=test1,
                branch="main",
                commit="abc123",
                status=Status.PASSED,
                final=True,
            )
            test2 = Test.objects.create(project=project, name="test2")
            Result.objects.create(
                test=test2,
                branch="main",
                commit="abc123",
                status=Status.FAILED,
                final=True,
            )

            health = Result.objects.get_health(project, "abc123")

            expect(health.total) == 2
            expect(health.state) == "failure"
            expect(health.description) == "1 of 2 passing"

        @pytest.mark.django_db
        def it_only_counts_final_results():
            test = Test.objects.create(project=project, name="test")
            Result.objects.create(
                test=test,
                branch="main",
                commit="abc123",
                status=Status.FAILED,
                final=False,
            )
            Result.objects.create(
                test=test,
                branch="main",
                commit="abc123",
                status=Status.PASSED,
                final=True,
            )

            health = Result.objects.get_health(project, "abc123")

            expect(health.total) == 1
            expect(health.state) == "success"
            expect(health.description) == "1 of 1 passing"

        @pytest.mark.django_db
        def it_identifies_new_failures():
            # Create tests and results for the default branch
            for i in range(3):
                test = Test.objects.create(
                    project=project,
                    name=f"test_{i+1}",
                )
                Result.objects.create(
                    test=test,
                    branch=project.default_branch,
                    commit="abc123",
                    status=Status.PASSED,
                    final=True,
                )

            # Create results for the commit we're checking, including a new failure
            for i, test in enumerate(Test.objects.all()):
                status = Status.FAILED if i == 0 else Status.PASSED
                result = Result.objects.create(
                    test=test,
                    branch="my-branch",
                    commit="def456",
                    status=status,
                    final=True,
                )
            health = Result.objects.get_health(project, "def456")
            expect(health.total) == 3
            expect(health.state) == "pending"
            expect(health.description) == "2 of 3 passing, 1 more result expected"

            # Simulate a release being finalized after a timeout
            health = Result.objects.get_health(project, "def456", final=True)
            expect(health.total) == 3
            expect(health.state) == "failure"
            expect(health.description) == "2 of 3 passing, 1 new failure"


def describe_run_manager(expect):
    @pytest.fixture
    def suite(project: Project):
        return Suite.objects.create(project=project, name="test-suite")

    def describe_track_step(expect, suite: Suite):
        @pytest.mark.django_db
        def with_full_lifecycle():
            # Setup step: creates run
            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="setup",
                metadata={"key": "value"},
            )

            expect(created) == True
            expect(run.setup_started_at).is_not(None)
            expect(run.tests_started_at).is_(None)
            expect(run.tests_finished_at).is_(None)
            expect(run.teardown_finished_at).is_(None)
            expect(run.metadata) == {"key": "value"}

            # Start step: sets tests_started_at
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="start",
                metadata={},
            )

            expect(created) == False
            expect(run.tests_started_at).is_not(None)
            expect(run.tests_finished_at).is_(None)

            # Finish step: sets tests_finished_at
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="finish",
                metadata={},
            )

            expect(created) == False
            expect(run.tests_finished_at).is_not(None)

            # Teardown step: sets teardown_finished_at and ensures tests_finished_at
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="teardown",
                metadata={},
            )

            expect(created) == False
            expect(run.teardown_finished_at).is_not(None)
            expect(run.tests_finished_at).is_not(None)

        @pytest.mark.django_db
        def with_finish_step_adjusts_teardown_if_in_past():
            now = timezone.now()
            tests_started = now - timedelta(minutes=5)
            tests_finished = now - timedelta(minutes=2)
            teardown_finished = now - timedelta(minutes=1)

            run: Run = Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=tests_started,
                tests_finished_at=tests_finished,
                teardown_finished_at=teardown_finished,
            )

            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="finish",
                metadata={},
            )

            expect(created) == False
            assert run.tests_finished_at, f"Invalid state: {run}"
            expected_teardown = run.tests_finished_at + (
                teardown_finished - tests_finished
            )
            expect(run.teardown_finished_at) == expected_teardown

        @pytest.mark.django_db
        def with_finish_step_overwrites_if_not_expired():
            original_time = timezone.now() - timedelta(minutes=1)
            Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=timezone.now() - timedelta(minutes=1),
                tests_finished_at=original_time,
            )

            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="finish",
                metadata={},
            )

            expect(run.tests_finished_at) > original_time

        @pytest.mark.django_db
        def with_finish_step_does_not_overwrite_if_expired():
            threshold = PENDING_THRESHOLD * 2
            expired_time = timezone.now() - threshold - timedelta(minutes=1)
            Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=expired_time,
                tests_finished_at=expired_time,
            )

            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="finish",
                metadata={},
            )

            expect(run.tests_finished_at) == expired_time

        @pytest.mark.django_db
        def with_teardown_step_sets_tests_finished_if_missing():
            Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=timezone.now(),
            )

            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="teardown",
                metadata={},
            )

            expect(run.tests_finished_at).is_not(None)

        @pytest.mark.django_db
        def with_teardown_step_overwrites_if_not_expired():
            original_time = timezone.now() - timedelta(minutes=1)
            Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=timezone.now() - timedelta(minutes=2),
                teardown_finished_at=original_time,
            )

            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="teardown",
                metadata={},
            )

            expect(run.teardown_finished_at) > original_time

        @pytest.mark.django_db
        def with_teardown_step_does_not_overwrite_if_expired():
            threshold = PENDING_THRESHOLD * 2
            expired_time = timezone.now() - threshold - timedelta(minutes=1)
            Run.objects.create(
                project=suite.project,
                suite=suite,
                branch="main",
                commit="abc123",
                tests_started_at=expired_time,
                teardown_finished_at=expired_time,
            )

            run: Run
            run, created = Run.objects.track_step(  # type: ignore[assignment]
                suite=suite,
                branch="main",
                commit="abc123",
                step="teardown",
                metadata={},
            )

            expect(run.teardown_finished_at) == expired_time
