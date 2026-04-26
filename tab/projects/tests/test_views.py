import json
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

import pytest

from ..constants import DEFAULT_SUITE
from ..helpers import (
    METRICS_JSON_RESULT_META,
    METRICS_JSON_TEST_META,
    build_metrics_json,
)
from ..models import Project, Result, Status, Suite, Test


def describe_build_metrics_json():
    @pytest.mark.django_db
    def it_includes_recent_results_nested_under_each_test(
        expect, admin_user, project: Project
    ):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        created = test.results.create(
            branch="main",
            commit="deadbeef",
            status=Status.PASSED,
            duration=2.5,
        )
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["message"]).contains("Test Analysis Bot")
        expect(payload["tests"][0]) == METRICS_JSON_TEST_META
        expect(len(payload["tests"])) == 2
        expect(len(payload["tests"][1]["results"])) == 2
        expect(payload["tests"][1]["results"][0]) == METRICS_JSON_RESULT_META
        expect(payload["tests"][1]["results"][1]["tab_id"]) == created.pk
        expect(payload["tests"][1]["results"][1]["branch"]) == "main"
        expect(payload["tests"][1]["results"][1]["commit"]) == "deadbeef"
        expect(payload["tests"][1]["results"][1]["test_duration"]) == 2.5
        expect(payload["tests"][1]["results"][1]["logs"]) == []

    @pytest.mark.django_db
    def it_includes_logs_on_results(expect, admin_user, project: Project):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        logs = [{"step": "pytest", "rc": 1}]
        test.results.create(
            branch="main",
            commit="deadbeef",
            status=Status.FAILED,
            duration=1.0,
            metadata={"logs": logs},
        )
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["tests"][1]["results"][1]["logs"]) == logs

    @pytest.mark.django_db
    def it_includes_suite_setup_duration_on_results(
        expect, admin_user, project: Project
    ):
        suite = Suite.objects.create(project=project, name=DEFAULT_SUITE)
        test = project.tests.create(
            name="my-test", suite=suite, disabled_user=admin_user
        )
        result = test.results.create(
            suite=suite,
            branch="main",
            commit="deadbeef",
            status=Status.PASSED,
            duration=1.0,
        )
        started = timezone.now() - timedelta(seconds=8)
        tests_started = started + timedelta(seconds=3)
        project.runs.create(
            suite=suite,
            branch=result.branch,
            commit=result.commit,
            setup_started_at=started,
            tests_started_at=tests_started,
        )

        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["tests"][1]["results"][1]["setup_duration"]) == 3.0

    @pytest.mark.django_db
    def it_includes_created_at_on_project_and_tests(expect, admin_user, project):
        test = project.tests.create(name="my-test", disabled_user=admin_user)

        def fmt_utc(dt):
            if dt and timezone.is_aware(dt):
                dt = dt.astimezone(dt_timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None

        project.refresh_from_db()
        test.refresh_from_db()
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["project"]["created_at"]) == fmt_utc(project.created_at)
        expect(payload["tests"][1]["created_at"]) == fmt_utc(test.created_at)

    @pytest.mark.django_db
    def it_includes_tab_id_and_tab_url_on_project(expect, admin_user, project):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["project"]["tab_id"]) == project.pk
        expect(
            payload["project"]["tab_url"]
            == settings.BASE_URL + reverse("projects:tests", args=[project.path])
        )

    @pytest.mark.django_db
    def it_includes_latest_pass_and_latest_failure_when_both_exist(
        expect, admin_user, project: Project
    ):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        fail = test.results.create(
            branch="main",
            commit="aaa",
            status=Status.FAILED,
            duration=1.0,
        )
        Result.objects.filter(pk=fail.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        passed = test.results.create(
            branch="main",
            commit="bbb",
            status=Status.PASSED,
            duration=1.0,
        )
        Result.objects.filter(pk=passed.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        payload = json.loads(build_metrics_json(project, [test]))
        statuses = {
            row["status"]
            for row in payload["tests"][1]["results"]
            if isinstance(row, dict)
        }
        expect(Status.FAILED.value in statuses)
        expect(Status.PASSED.value in statuses)

    @pytest.mark.django_db
    def it_caps_exported_results_at_ten(expect, admin_user, project: Project):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        base = timezone.now()
        for i in range(15):
            r = test.results.create(
                branch="main",
                commit=f"c{i}",
                status=Status.PASSED,
                duration=1.0,
            )
            Result.objects.filter(pk=r.pk).update(
                created_at=base - timedelta(minutes=i)
            )

        payload = json.loads(build_metrics_json(project, [test]))
        expect(len(payload["tests"][1]["results"])) == 11

    @pytest.mark.django_db
    def it_serializes_empty_results_when_test_has_none(
        expect, admin_user, project: Project
    ):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        payload = json.loads(build_metrics_json(project, [test]))
        row = payload["tests"][1]
        expect(row["results"]) == []
        expect(row["markers"]) == []
        expect(row["command"]) is None

    @pytest.mark.django_db
    def it_includes_markers_and_command_only_on_test(
        expect, admin_user, project: Project
    ):
        suite = Suite.objects.create(
            project=project,
            name=DEFAULT_SUITE,
            local_command="pytest {test.name}",
        )
        test = project.tests.create(
            name="my-test", suite=suite, disabled_user=admin_user
        )
        test.results.create(
            branch="main",
            commit="deadbeef",
            status=Status.PASSED,
            duration=2.5,
            suite=suite,
            metadata={"annotations": ["slow"]},
        )
        test.refresh_from_db()
        payload = json.loads(build_metrics_json(project, [test]))
        row = payload["tests"][1]
        res = row["results"][1]
        expect(payload["tests"][0]) == METRICS_JSON_TEST_META
        expect(row["results"][0]) == METRICS_JSON_RESULT_META
        expect(row["markers"]) == ["slow"]
        expect(row["command"]) == "pytest my-test"
        expect("markers" in res) == False
        expect("command" in res) == False

    @pytest.mark.django_db
    def it_includes_default_branch_under_project(expect, admin_user, project: Project):
        project.default_branches = ["staging", "production"]
        project.save(update_fields=["default_branches"])
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["project"]["default_branch"]) == "staging"

    @pytest.mark.django_db
    def it_includes_original_branch_and_commit(expect, admin_user, project: Project):
        test = project.tests.create(
            name="my-test",
            disabled_user=admin_user,
            original_branch="feature/x",
            original_commit="abc123def",
        )
        payload = json.loads(build_metrics_json(project, [test]))
        row = payload["tests"][1]
        expect(row["original_branch"]) == "feature/x"
        expect(row["original_commit"]) == "abc123def"

    @pytest.mark.django_db
    def it_serializes_empty_original_branch_and_commit_as_null(
        expect, admin_user, project: Project
    ):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        payload = json.loads(build_metrics_json(project, [test]))
        row = payload["tests"][1]
        expect(row["original_branch"]) == None
        expect(row["original_commit"]) == None


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


@pytest.fixture
def disabled_test(project: Project):
    test = Test.objects.create(project=project, name="test")
    test.results.create(
        branch="main",
        commit="abc123",
        status=Status.PASSED,
        duration=1.0,
    )
    test.disabled_at = timezone.now()
    test.failure_rate = 0.25
    test.save()
    return test


def describe_projects():
    url = "/projects/foo/bar"

    @pytest.mark.django_db
    def it_renders_the_projects_page(expect, admin_client, project: Project):
        response = admin_client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("foo › bar")
        expect(html).contains("0 tests")


def describe_tests():
    url = "/projects/foo/bar/tests"

    def it_redirects_tag_search_to_query_param(expect, admin_client):
        response = admin_client.get(f"{url}?search=foobar tag:@FIXME")
        expect(response.status_code) == 302
        expect(response.url) == f"{url}?search=foobar&tag=fixme"

    def describe_details():
        url = "/projects/foo/bar/tests/{pk}"

        @pytest.mark.django_db
        def it_renders_the_test_details_page(expect, admin_client, disabled_test: Test):
            response = admin_client.get(url.format(pk=disabled_test.pk))
            expect(response.status_code) == 200

        @pytest.mark.django_db
        def it_updates_override_behavior(
            expect, mocker, admin_client, admin_user, disabled_test: Test
        ):
            mocker.patch("tab.projects.views.Alert")  # silence thread warnings

            # Create a test in a parent suite
            parent_project = Project.objects.create(
                repository="https://github.com/foo/bar/parent"
            )
            parent_suite = Suite.objects.create(
                project=parent_project, name="parent suite"
            )
            parent_test = Test.objects.create(
                project=parent_project,
                suite=parent_suite,
                name=disabled_test.name,
            )

            # Update the main test
            suite = Suite.objects.create(
                project=disabled_test.project,
                name="suite",
                parent=parent_suite,
            )
            disabled_test.suite = suite
            disabled_test.save()

            # Create a test in a child suite
            child_project = Project.objects.create(
                repository="https://github.com/foo/bar/child"
            )
            child_suite = Suite.objects.create(
                project=child_project,
                name="child suite",
                parent=parent_suite,
            )
            child_test = Test.objects.create(
                project=child_project,
                suite=child_suite,
                name=disabled_test.name,
                disabled_reason="bar",
            )

            # Disable the test
            response = admin_client.post(
                url.format(pk=disabled_test.pk),
                data={
                    "test_id": str(disabled_test.pk),
                    "disabled": "on",
                    "disabled_reason": "foo",
                    "disabled_user": admin_user.email,
                },
            )
            expect(response.status_code) == 302
            disabled_test.refresh_from_db()
            expect(disabled_test.disabled_at).is_not(None)
            expect(disabled_test.disabled_reason) == "foo"
            expect(disabled_test.disabled_user) == admin_user
            expect(response.url) == url.format(pk=disabled_test.pk)

            # Check the sibling tests
            parent_test.refresh_from_db()
            expect(parent_test.disabled_at).is_not(None)
            expect(parent_test.disabled_reason) == "foo"
            expect(parent_test.disabled_user) == admin_user
            child_test.refresh_from_db()
            expect(child_test.disabled_at).is_not(None)
            expect(child_test.disabled_reason) == "bar"  # preserves message
            expect(child_test.disabled_user) == admin_user

            # Restore the test
            response = admin_client.post(
                url.format(pk=disabled_test.pk),
                data={
                    "test_id": str(disabled_test.pk),
                    "disabled_reason": "",
                    "disabled_user": admin_user.email,
                },
            )
            expect(response.status_code) == 302
            disabled_test.refresh_from_db()
            expect(disabled_test.disabled_at).is_(None)
            expect(disabled_test.disabled_reason) == ""
            expect(disabled_test.disabled_user) == admin_user
            expect(response.url) == url.format(pk=disabled_test.pk)

            # Check the sibling tests
            parent_test.refresh_from_db()
            expect(parent_test.disabled_at).is_not(None)  # preserves state
            expect(parent_test.disabled_reason) == "foo"  # preserves message
            expect(parent_test.disabled_user) == admin_user
            child_test.refresh_from_db()
            expect(child_test.disabled_at).is_not(None)  # preserves state
            expect(child_test.disabled_reason) == "bar"  # preserves message
            expect(child_test.disabled_user) == admin_user

    def describe_disabled():
        url = "/projects/foo/bar/tests/disabled"

        @pytest.mark.django_db
        def it_renders_the_disabled_tests_page(
            expect, admin_client, disabled_test: Test
        ):
            response = admin_client.get(url)
            expect(response.status_code) == 200
            html = response.content.decode("utf-8")
            expect(html).contains("1 Disabled Test")

        def describe_regex():
            url = "/projects/foo/bar/tests/disabled/regex"

            @pytest.mark.django_db
            def it_joins_the_regex_for_each_test(
                expect, client, project: Project, disabled_test: Test
            ):
                for name in ["test [abc]", "test's name"]:
                    test = Test.objects.create(project=project, name=name)
                    test.results.create(
                        branch="main",
                        commit="abc123",
                        status=Status.PASSED,
                        duration=1.0,
                    )
                    test.disabled_at = timezone.now()
                    test.failure_rate = 0.25
                    test.save()

                response = client.get(url)
                expect(response.status_code) == 200
                text = response.content.decode("utf-8")
                expect(text) == r"'test|test \[abc\]|test'\''s name'"


def describe_results():
    url = "/projects/foo/bar/results"

    @pytest.mark.django_db
    def it_renders_the_results_page(expect, admin_client, project: Project):
        Result.objects.create(
            test=Test.objects.create(project=project, name="test"),
            branch="main",
            commit="abc123",
            status=Status.PASSED,
            duration=1.0,
        )

        response = admin_client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("(1 result)")

    def it_redirects_platform_search_to_query_param(expect, admin_client):
        response = admin_client.get(f"{url}?search=foo PLATFORM:Windows bar")
        expect(response.status_code) == 302
        expect(response.url) == f"{url}?search=foo+bar&platform=windows"

    def it_redirects_tag_search_to_query_param(expect, admin_client):
        response = admin_client.get(f"{url}?search=foobar tag:@FIXME")
        expect(response.status_code) == 302
        expect(response.url) == f"{url}?search=foobar&tag=fixme"

    def describe_regex():
        url = "/projects/foo/bar/results/regex"

        @pytest.mark.django_db
        def it_joins_the_regex_for_each_results_test(
            expect, admin_client, project: Project
        ):
            test1 = Test.objects.create(project=project, name="failing test")
            test1.results.create(
                branch="main",
                commit="abc123",
                status=Status.FAILED,
            )
            test2 = Test.objects.create(project=project, name="errored test")
            test2.results.create(
                branch="main",
                commit="abc123",
                status=Status.ERROR,
            )
            test3 = Test.objects.create(project=project, name="passing test")
            test3.results.create(
                branch="main",
                commit="abc123",
                status=Status.PASSED,
            )

            response = admin_client.get(url + "?show=fails")
            expect(response.status_code) == 200
            html = response.content.decode("utf-8")
            expect(html) == r"'errored test|failing test'"


def describe_metrics():
    url = "/projects/foo/bar/metrics"

    @pytest.mark.django_db
    def it_renders_the_metrics_page(expect, admin_client, admin_user, project: Project):
        project.tests.create(name="my-test", disabled_user=admin_user)

        response = admin_client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains(admin_user.email)

    @pytest.mark.django_db
    def it_downloads_ai_data_json(expect, admin_client, admin_user, project: Project):
        project.tests.create(name="my-test", disabled_user=admin_user)

        response = admin_client.get("/projects/foo/bar/metrics/download.json")
        expect(response.status_code) == 200
        expect(response["Content-Type"]).contains("application/json")
        expect(response["Content-Disposition"]).contains("attachment")
        expect(response["Content-Disposition"]).contains("tab-ai-data-foo-bar.json")
        body = response.content.decode("utf-8")
        expect(body).contains('"name": "foo › bar"')

    @pytest.mark.django_db
    def it_renders_metrics_raw_preview(
        expect, admin_client, admin_user, project: Project
    ):
        project.tests.create(name="my-test", disabled_user=admin_user)

        response = admin_client.get("/projects/foo/bar/metrics/raw")
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("AI Data")
        expect(html).contains("&quot;name&quot;: &quot;foo › bar&quot;")
