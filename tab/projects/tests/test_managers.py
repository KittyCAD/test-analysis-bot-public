from django.utils import timezone

import pytest

from ..models import Project, Result, Status, Test


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


def describe_result_manager():
    def describe_get_health():
        @pytest.mark.django_db
        def it_returns_health_metrics(expect, project: Project):
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
            test3 = Test.objects.create(project=project, name="test2")
            Result.objects.create(
                test=test3,
                branch="main",
                commit="abc123",
                status=Status.FAILED,
                final=True,
            )
            test3.failure_rate = 0.09
            test3.save()

            health = Result.objects.get_health(project, "abc123")

            expect(health.total) == 3
            expect(health.state) == "failure"
            expect(health.description) == "1 of 3 passing, 1 new failure"

        @pytest.mark.django_db
        def it_only_counts_final_results(expect, project: Project):
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
        def it_identifies_new_failures(expect, project: Project):
            # Create tests and results for the default branch
            for i in range(4):
                test = Test.objects.create(
                    project=project,
                    name=f"test_{i}",
                    updated_at=timezone.now(),
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
                Result.objects.create(
                    test=test,
                    branch="my-branch",
                    commit="def456",
                    status=status,
                    final=True,
                )
                # Set failure rate to 0 for the failing test after creating the result
                if i == 0:
                    test.failure_rate = 0.0
                    test.save()

            health = Result.objects.get_health(project, "def456")

            expect(health.total) == 4
            expect(health.state) == "failure"
            expect(health.description) == "3 of 4 passing, 1 new failure"
