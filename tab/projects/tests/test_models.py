import pytest

from ..enums import Status
from ..models import Project, Result, Test


def describe_project():
    def it_formats_name(expect):
        project = Project(repository="https://github.com/MyUser/my_repo")
        expect(project.name) == "MyUser › my_repo"


def describe_test():
    @pytest.fixture
    def project():
        return Project.objects.create(repository="https://github.com/foo/bar")

    def describe_update_failure_rate():
        @pytest.mark.django_db
        def it_returns_false_if_no_results(expect, project: Project):
            test = project.test_set.create(name="my-test")
            expect(test.update_failure_rate()) == False

        @pytest.mark.django_db
        def it_computes_failure_rate(expect, project: Project):
            test: Test = project.test_set.create(
                name="my-test", original_branch="my-branch"
            )
            test.result_set.create(test=test, status=Status.PASSED, branch="my-branch")
            test.result_set.create(test=test, status=Status.FAILED, branch="main")
            test.result_set.create(test=test, status=Status.FAILED, branch="main")
            test.result_set.create(test=test, status=Status.FAILED, branch="other")

            test.failure_rate = -1
            expect(test.update_failure_rate()) == True
            expect(test.failure_rate) == 0.667

    def describe_update_average_duration():
        @pytest.mark.django_db
        def it_returns_false_if_no_results(expect, project: Project):
            test: Test = project.test_set.create(name="my-test")
            expect(test.update_average_duration()) == False

        @pytest.mark.django_db
        def it_computes_average_duration(expect, project: Project):
            test: Test = project.test_set.create(
                name="my-test", original_branch="my-branch"
            )
            test.result_set.create(
                test=test, status=Status.PASSED, branch="my-branch", duration=2
            )
            test.result_set.create(
                test=test, status=Status.FAILED, branch="main", duration=3
            )
            test.result_set.create(
                test=test, status=Status.FAILED, branch="other", duration=4
            )

            test.average_duration = -1
            expect(test.update_average_duration()) == True
            expect(test.average_duration) == 2.5


def describe_result():
    def describe_save():
        @pytest.mark.django_db
        def it_cleans_message(expect):
            test = Project.objects.create(
                repository="https://github.com/foo/bar"
            ).test_set.create(name="test")
            result = Result.objects.create(
                test=test,
                status="failed",
                branch="main",
                commit="abc123",
                message="Error: [31mTimed out 5000ms waiting for [39m[2mexpect([22m[31mlocator[39m[2m).[22mnot[2m.[22mtoBeDisabled[2m()[22m",
            )
            expect(
                result.message
            ) == "Error: Timed out 5000ms waiting for expect(locator).not.toBeDisabled()"
