import json
from datetime import timedelta

from django.utils import timezone

import pytest

from ..helpers import build_metrics_json
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
        expect(payload["_meta"]).contains("Test Analysis Bot")
        expect(payload["tests"][0]["_meta"]).contains("least-reliable")
        expect(len(payload["tests"])) == 1
        expect(len(payload["tests"][0]["results"])) == 1
        expect(payload["tests"][0]["results"][0]["id"]) == created.pk
        expect(payload["tests"][0]["results"][0]["branch"]) == "main"
        expect(payload["tests"][0]["results"][0]["commit"]) == "deadbeef"

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
        statuses = {row["status"] for row in payload["tests"][0]["results"]}
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
        expect(len(payload["tests"][0]["results"])) == 10

    @pytest.mark.django_db
    def it_serializes_empty_results_when_test_has_none(
        expect, admin_user, project: Project
    ):
        test = project.tests.create(name="my-test", disabled_user=admin_user)
        payload = json.loads(build_metrics_json(project, [test]))
        expect(payload["tests"][0]["results"]) == []


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
        expect(body).contains('"repository": "foo/bar"')

    @pytest.mark.django_db
    def it_renders_metrics_raw_preview(
        expect, admin_client, admin_user, project: Project
    ):
        project.tests.create(name="my-test", disabled_user=admin_user)

        response = admin_client.get("/projects/foo/bar/metrics/raw")
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("AI Data")
        expect(html).contains("repository")
