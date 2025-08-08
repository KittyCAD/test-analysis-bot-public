from datetime import timedelta

import log
import pytest

from ..constants import DEFAULT_SUITE, FAILURE_RATE_EPSILON
from ..enums import Platform, Status
from ..models import Project, Result, Suite, Test
from . import EXAMPLE_TESTS, ExampleTest


def describe_project():
    def it_formats_name(expect):
        project = Project(repository="https://github.com/MyUser/my_repo")
        expect(project.name) == "MyUser › my_repo"


def describe_suite():
    def describe_str():
        def it_formats_name(expect):
            suite = Suite(
                project=Project(repository="https://github.com/MyUser/my_repo"),
                name="my_suite",
            )
            expect(str(suite)) == "MyUser › my_repo › my_suite"

        def it_formats_name_with_default(expect):
            suite = Suite(
                project=Project(repository="https://github.com/MyUser/my_repo"),
                name=DEFAULT_SUITE,
            )
            expect(str(suite)) == "MyUser › my_repo"


def describe_test():
    @pytest.fixture
    def project():
        return Project(repository="https://github.com/foo/bar")

    @pytest.fixture
    def suite(project):
        return Suite(project=project, name="my-suite")

    def describe_str():
        def it_formats_name(expect, project):
            test = Test(project=project, name="my-test")
            expect(str(test)) == "my-test"

        def it_formats_name_with_suite(expect, project, suite):
            test = Test(project=project, suite=suite, name="my-test")
            expect(str(test)) == "my-suite › my-test"

        def it_formats_name_with_default_suite(expect, project, suite):
            suite.name = DEFAULT_SUITE
            test = Test(project=project, suite=suite, name="my-test")
            expect(str(test)) == "my-test"

    def describe_regex():
        @pytest.mark.parametrize(("example_test"), EXAMPLE_TESTS)
        def it_escapes_special_characters(expect, example_test: ExampleTest):
            log.debug(f"{example_test.case} case: {example_test.name!r}")
            log.debug(f"Expected regex: {example_test.regex!r}")
            if not example_test.regex:
                pytest.skip("No example regex provided for this case")
            test = Test(name=example_test.name)
            log.debug(f"Actual regex: {test.regex!r}")
            expect(test.regex) == example_test.regex

    def describe_substring():
        @pytest.mark.parametrize(("example_test"), EXAMPLE_TESTS)
        def it_returns_plain_words(expect, example_test: ExampleTest):
            log.debug(f"{example_test.case} case: {example_test.name!r}")
            log.debug(f"Expected substring: {example_test.substring!r}")
            if not example_test.substring:
                pytest.skip("No example substring provided for this case")
            test = Test(name=example_test.name)
            log.debug(f"Actual substring: {test.substring!r}")
            expect(test.substring) == example_test.substring

    def describe_disabled():
        @pytest.mark.django_db
        def it_is_set_if_disabled_for_any_platform(expect, project: Project):
            project.save()
            test = Test.objects.create(
                project=project, name="my-test", disabled_platforms=[Platform.WINDOWS]
            )
            expect(test.disabled) == True

        @pytest.mark.django_db
        def it_is_cleared_after_zero_failures(expect, admin_user, project: Project):
            project.save()
            test = Test.objects.create(
                project=project,
                name="my-test",
                disabled=True,
                disabled_user=admin_user,
                failure_rate=0.25,
            )
            expect(test.disabled) == True

            test.failure_rate = 0
            test.save()
            expect(test.disabled) == False
            expect(test.disabled_platforms) == []
            expect(test.disabled_user) == admin_user

    def describe_enabled():
        @pytest.mark.django_db
        def it_is_true_if_last_result(expect, project: Project):
            project.save()
            test = Test.objects.create(project=project, name="my-test")
            test.results.create(test=test, branch="main", status=Status.PASSED)
            expect(test.enabled) == True

        @pytest.mark.django_db
        def it_is_false_if_last_result_is_skipped(expect, project: Project):
            project.save()
            test = Test.objects.create(project=project, name="my-test")
            test.results.create(test=test, branch="main", status=Status.SKIPPED)
            expect(test.enabled) == False

        @pytest.mark.django_db
        def it_is_true_if_any_results_for_latest_commit(expect, project: Project):
            project.save()
            test = Test.objects.create(project=project, name="my-test")
            test.results.create(
                test=test, branch="main", commit="abc123", status=Status.PASSED
            )
            test.results.create(
                test=test, branch="main", commit="abc123", status=Status.SKIPPED
            )
            expect(test.enabled) == True

    def describe_significant_branches():
        def it_includes_default_and_original_branches(expect):
            project = Project(
                repository="https://github.com/foo/bar",
                default_branches=["staging", "production"],
            )
            expect(project.default_branches) == ["staging", "production"]
            test = Test(project=project, name="my-test", original_branch="my-branch")
            expect(test.significant_branches) == ["my-branch", "staging", "production"]
            expect(project.default_branch) == "staging"

    def describe_update_failure_rate():
        @pytest.mark.django_db
        def it_returns_false_if_no_results(expect, project: Project):
            project.save()
            test = project.tests.create(name="my-test")
            expect(test.update_failure_rate()) == False
            expect(test.update_block_rate()) == False

        @pytest.mark.django_db
        def it_computes_failure_rate(expect, project: Project):
            project.save()
            test: Test = project.tests.create(
                name="my-test", original_branch="my-branch"
            )
            test.results.create(
                test=test, status=Status.PASSED, branch="my-branch", commit="a1"
            )
            test.results.create(
                test=test, status=Status.SKIPPED, branch="main", commit="b2"
            )
            test.results.create(
                test=test, status=Status.FAILED, branch="main", commit="b2"
            )
            test.results.create(
                test=test, status=Status.FAILED, branch="other", commit="c3"
            )

            test.failure_rate = -1
            expect(test.update_failure_rate()) == True
            expect(test.failure_rate) == 0.333333

            test.block_rate = -1
            expect(test.update_block_rate()) == True
            expect(test.block_rate) == 0.5

        @pytest.mark.django_db
        def it_stays_above_zero_if_recent_branch_failures(expect, project: Project):
            project.save()
            test: Test = project.tests.create(name="my-test")
            test.results.create(test=test, status=Status.PASSED, branch="main")
            test.results.create(test=test, status=Status.FAILED, branch="other")
            expect(test.failure_rate) == FAILURE_RATE_EPSILON

    def describe_update_average_duration():
        @pytest.mark.django_db
        def it_returns_false_if_no_results(expect, project: Project):
            project.save()
            test: Test = project.tests.create(name="my-test")
            expect(test.update_average_duration()) == False

        @pytest.mark.django_db
        def it_computes_average_duration(expect, project: Project):
            project.save()
            test: Test = project.tests.create(
                name="my-test", original_branch="my-branch"
            )
            test.results.create(
                test=test, status=Status.PASSED, branch="my-branch", duration=2
            )
            test.results.create(
                test=test, status=Status.FAILED, branch="main", duration=3
            )
            test.results.create(
                test=test, status=Status.FAILED, branch="other", duration=4
            )

            test.average_duration = -1
            expect(test.update_average_duration()) == True
            expect(test.average_duration) == 2.5


def describe_result():
    def describe_markers():

        def it_adds_disabled_marker_if_test_is_disabled(expect):
            test = Test(name="test", disabled=True)
            result = Result(test=test, status=Status.FAILED)
            expect(result.markers) == ["disabled"]

        def it_adds_disabled_marker_if_test_is_disabled_on_platform(expect):
            test = Test(name="test", disabled_platforms=[Platform.WINDOWS])
            result = Result(test=test, status=Status.FAILED, platform=Platform.WINDOWS)
            expect(result.markers) == ["disabled"]

        def it_does_not_add_disabled_marker_if_another_platform(expect):
            test = Test(name="test", disabled_platforms=[Platform.WINDOWS])
            result = Result(test=test, status=Status.FAILED, platform=Platform.MACOS)
            expect(result.markers) == []

    def describe_command():
        def it_includes_checkout_command(expect):
            test = Test(name="my-test")
            suite = Suite(name="my-suite", local_command="pytest {test.name}")
            result = Result(test=test, branch="my-branch", suite=suite)
            expect(result.command) == [
                (
                    "git fetch origin && git checkout my-branch && git reset --hard origin/my-branch",
                    True,
                ),
                ("\n", False),
                ("# then", False),
                ("\n", False),
                ("pytest my-test", True),
            ]

    def describe_originated_from_branch():
        def it_detects_if_branch_is_original_and_not_default(expect):
            project = Project()

            test = Test(project=project, name="test1", original_branch="my-branch")
            result = Result(test=test, branch="my-branch")
            expect(result.originated_from_branch) == True

            test = Test(project=project, name="test2", original_branch="my-branch")
            result = Result(test=test, branch="main")
            expect(result.originated_from_branch) == False

            test = Test(project=project, name="test3", original_branch="main")
            result = Result(test=test, branch="main")
            expect(result.originated_from_branch) == False

    def describe_run_url():
        def it_includes_run_id_and_pr_number(expect):
            result = Result(
                test=Test(project=Project(repository="https://github.com/foo/bar")),
                branch="main",
                metadata={"GITHUB_RUN_ID": "123", "CI_PR_NUMBER": "456"},
            )
            expect(
                result.run_url
            ) == "https://github.com/foo/bar/actions/runs/123?pr=456"

    def describe_finalize():
        @pytest.mark.django_db
        def it_demotes_recent_results_for_same_commit_on_main(expect):
            project = Project.objects.create(repository="https://github.com/foo/bar")
            test = project.tests.create(name="my-test")

            # Create a result from an hour ago
            result = test.results.create(
                test=test, status=Status.PASSED, branch="main", commit="a1"
            )
            result.created_at = result.created_at - timedelta(hours=1)
            result.save()
            # Create a result from now with a rerun
            test.results.create(
                test=test, status=Status.FAILED, branch="main", commit="a1"
            )
            test.results.create(
                test=test, status=Status.PASSED, branch="main", commit="a1"
            )

            # Expect one final result from each hourly run
            expect(test.results.filter(final=True).count()) == 2

        @pytest.mark.django_db
        def it_demotes_all_results_for_same_commit_on_branches(expect):
            project = Project.objects.create(repository="https://github.com/foo/bar")
            test = project.tests.create(name="my-test")

            # Create a result from an hour ago
            result = test.results.create(
                test=test, status=Status.PASSED, branch="my-branch", commit="a1"
            )
            result.created_at = result.created_at - timedelta(hours=1)
            result.save()
            # Create a result from now with a rerun
            test.results.create(
                test=test, status=Status.FAILED, branch="my-branch", commit="a1"
            )
            test.results.create(
                test=test, status=Status.PASSED, branch="my-branch", commit="a1"
            )

            # Expect only one final result
            expect(test.results.filter(final=True).count()) == 1

    def describe_save():
        @pytest.mark.django_db
        def it_cleans_message(expect):
            test = Project.objects.create(
                repository="https://github.com/foo/bar"
            ).tests.create(name="test")
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
