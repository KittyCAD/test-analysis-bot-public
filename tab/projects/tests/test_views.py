import pytest

from ..models import Project, Result, Status, Test


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
    test.disabled = True
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
        def it_renders_the_test_details_page(
            expect, admin_client, project: Project, disabled_test: Test
        ):
            response = admin_client.get(url.format(pk=disabled_test.pk))
            expect(response.status_code) == 200

    def describe_disabled():
        url = "/projects/foo/bar/tests/disabled"

        @pytest.mark.django_db
        def it_renders_the_disabled_tests_page(
            expect, admin_client, project: Project, disabled_test: Test
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
                    test.disabled = True
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
        expect(html).contains("1 of 1 passing")

    def it_redirects_platform_search_to_query_param(expect, admin_client):
        response = admin_client.get(f"{url}?search=foo PLATFORM:Windows bar")
        expect(response.status_code) == 302
        expect(response.url) == f"{url}?search=foo+bar&platform=windows"

    def it_redirects_tag_search_to_query_param(expect, admin_client):
        response = admin_client.get(f"{url}?search=foobar tag:@FIXME")
        expect(response.status_code) == 302
        expect(response.url) == f"{url}?search=foobar&tag=fixme"


def describe_metrics():
    url = "/projects/foo/bar/metrics"

    @pytest.mark.django_db
    def it_renders_the_metrics_page(expect, admin_client, admin_user, project: Project):
        project.tests.create(name="my-test", disabled_user=admin_user)

        response = admin_client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains(admin_user.email)
