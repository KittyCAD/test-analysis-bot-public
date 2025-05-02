import pytest

from ..models import Project, Result, Status, Test


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


def describe_result_manager():
    def describe_get_branch_health():
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

            total, state, description = Result.objects.get_branch_health(
                project, "main", "abc123"
            )

            expect(total) == 2
            expect(state) == "failure"
            expect(description) == "1 of 2 tests are passing"

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

            total, state, description = Result.objects.get_branch_health(
                project, "main", "abc123"
            )

            expect(total) == 1
            expect(state) == "success"
            expect(description) == "1 of 1 tests are passing"
