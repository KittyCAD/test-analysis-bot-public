import json
from pathlib import Path

import log
import pytest

from tab.core.models import Organization
from tab.projects.models import Result, Test


def post_json(client, url: str, data: dict):
    log.info(f"POST {url}: {data}")
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"X-API-Key": "fake-api-key"},
    )
    try:
        log.info(f"{response.status_code} response: {response.json()}")
    except ValueError:
        log.info(f"{response.status_code} response: {response.text}")
    return response


def post_form(client, url: str, data: dict):
    log.info(f"POST {url}: {data}")
    response = client.post(
        url,
        data=data,
        headers={"X-API-Key": "fake-api-key"},
    )
    try:
        log.info(f"{response.status_code} response: {response.json()}")
    except ValueError:
        log.info(f"{response.status_code} response: {response.text}")
    return response


def describe_results():

    url = "/api/results"

    @pytest.fixture
    def payload():
        return {
            "project": "https://github.com/my-user/my-project",
            "branch": "main",
            "commit": "abc123",
            "test": "my feature › my test",
            "status": "passed",
        }

    @pytest.mark.django_db
    def it_creates_projects_and_tests_automatically(expect, client, payload):
        response = post_json(client, url, payload)

        expect(response.status_code) == 201
        expect(response.json()) == {
            "project": "my-user › my-project",
            "test": "my feature › my test",
            "status": "passed",
            "block": False,
        }

    @pytest.mark.parametrize(
        "project",
        [
            "https://github.com/my-user",
            "github.com/my-user/my-project",
            "my-user/my-project",
        ],
    )
    def it_rejects_invalid_repositories(expect, client, payload, project):
        payload["project"] = project
        response = post_json(client, url, payload)

        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": f"Invalid repository URL: {project}",
        }

    @pytest.mark.django_db
    def it_updates_existing_test(expect, client, payload):
        local_payload = payload.copy()
        local_payload["branch"] = ""
        local_payload["commit"] = ""
        response = post_json(client, url, local_payload)
        test = Test.objects.get()

        expect(response.status_code) == 201
        expect(response.json()) == {
            "project": "my-user › my-project",
            "test": "my feature › my test",
            "status": "passed",
            "block": False,
        }
        expect(test.original_branch) == ""
        expect(test.original_commit) == ""

        response = post_json(client, url, payload)
        test.refresh_from_db()

        expect(response.status_code) == 200
        expect(test.original_branch) == "main"
        expect(test.original_commit) == "abc123"


def describe_bulk_results():
    url = "/api/results/bulk"

    @pytest.fixture
    def payload():
        junit_xml = Path(__file__).parent / "files" / "junit.xml"
        return {
            "project": "https://github.com/my-user/my-project",
            "branch": "main",
            "commit": "abc123",
            "tests": junit_xml.open("rb"),
            "EXTRA": "foobar",
        }

    @pytest.mark.django_db
    def it_creates_tests_from_junit_xml(expect, client, payload):
        response = post_form(client, url, payload)
        expect(response.json()) == {
            "project": "my-user › my-project",
            "branch": "main",
            "commit": "abc123",
            "tests": 25,
        }
        test: Test = Test.objects.first()  # type: ignore[assignment]
        expect(test.original_branch) == "main"
        expect(test.original_commit) == "abc123"
        expect(test.metadata) == {"EXTRA": "foobar"}
        result: Result = Result.objects.first()  # type: ignore[assignment]
        expect(result.branch) == "main"
        expect(result.commit) == "abc123"
        expect(result.metadata) == {"EXTRA": "foobar"}

    @pytest.mark.django_db
    def it_requires_tests_as_file_upload(expect, client, payload):
        del payload["tests"]
        response = post_form(client, url, payload)
        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": "Include 'tests' as a JUnit XML file upload.",
        }


def describe_share():

    url = "/api/share"

    @pytest.fixture
    def payload():
        return {
            "project": "https://github.com/my-user/my-project",
            "branch": "my-branch",
            "commit": "abc123",
        }

    @pytest.mark.django_db
    def it_updates_status(expect, client, payload, mocker):
        mock_github = mocker.patch("tab.api.helpers.Github")
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_commit = mock_repo.get_commit.return_value
        mock_create_status = mock_commit.create_status

        Organization.objects.create(
            name="MyOrganization",
            key="fake-api-key",
            repository_index="https://github.com/my-user",
            repository_token="fake-token",
        )

        response = post_json(client, url, payload)

        expect(response.status_code) == 200
        expect(response.json()) == {
            "project": "my-user › my-project",
            "branch": "my-branch",
            "commit": "abc123",
            "tests": 0,
        }
        expect(mock_create_status.call_args) == mocker.call(
            state="success",
            target_url="http://testserver.com/projects/my-user/my-project/results?branch=my-branch&show=fails",
            description="0 of 0 passing",
            context="Test Analysis Bot",
        )

    @pytest.mark.parametrize(
        "project",
        [
            "https://github.com/my-user",
            "github.com/my-user/my-project",
            "my-user/my-project",
        ],
    )
    @pytest.mark.django_db
    def it_rejects_invalid_repositories(expect, client, payload, project):
        Organization.objects.create(name="MyOrganization", key="fake-api-key")

        payload["project"] = project
        response = post_json(client, url, payload)

        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": f"Invalid repository URL: {project}",
        }
