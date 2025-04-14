import pytest

from ..models import Project


@pytest.fixture
def project():
    return Project.objects.create(repository="https://github.com/foo/bar")


def describe_projects():
    url = "/projects/foo/bar"

    @pytest.mark.django_db
    def it_renders_the_projects_page(expect, client, project: Project):
        response = client.get(url)
        expect(response.status_code) == 200
        html = response.content.decode("utf-8")
        expect(html).contains("foo › bar")
