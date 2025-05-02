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
        def it_returns_pending_if_less_than_half_of_tests_are_active(
            expect, project: Project
        ):
            for i in range(3):
                Test.objects.create(
                    project=project,
                    name=f"test_{i}",
                    updated_at=timezone.now(),
                )
            test = Test.objects.first()
            Result.objects.create(
                test=test,
                branch="main",
                commit="abc123",
                status=Status.FAILED,
                final=True,
            )

            health = Result.objects.get_health(project, "abc123")

            expect(health.total) == 1
            expect(health.state) == "pending"
            expect(health.description) == "0 of 1 passing"
