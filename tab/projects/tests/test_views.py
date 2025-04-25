import pytest

from ..models import Project, Test


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


@pytest.fixture
def test(project: Project):
    return Test.objects.create(project=project, name="test")


def describe_projects():
    url = "/projects/foo/bar"

    @pytest.mark.django_db
    def it_renders_the_projects_page(expect, client, project: Project):
        response = client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("foo › bar")
        expect(html).contains("0 tests")


def describe_tests():
    def describe_details():
        url = "/projects/foo/bar/tests/{pk}"

        @pytest.mark.django_db
        def it_renders_the_test_details_page(
            expect, client, project: Project, test: Test
        ):
            response = client.get(url.format(pk=test.pk))
            expect(response.status_code) == 200

    def describe_disabled():
        url = "/projects/foo/bar/tests/disabled"

        @pytest.mark.django_db
        def it_renders_the_disabled_tests_page(
            expect, client, project: Project, test: Test
        ):
            response = client.get(url)
            expect(response.status_code) == 200
            html = response.content.decode("utf-8")
            expect(html).contains("1 Disabled Test")


def describe_results():
    url = "/projects/foo/bar/results"

    @pytest.mark.django_db
    def it_renders_the_results_page(expect, client, project: Project):
        response = client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("0 results")
