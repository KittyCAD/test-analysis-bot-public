import json

import log
import pytest

from tab.projects.models import Test


def post(client, url: str, data: dict):
    log.info(f"POST {url}: {data}")
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={
            "X-API-Key": "my-api-key",
        },
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
        response = post(client, url, payload)

        expect(response.status_code) == 201
        expect(response.json()) == {
            "project": "my-user › my-project",
            "test": "my feature › my test",
            "result": "passed",
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
        response = post(client, url, payload)

        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": f"Invalid repository URL: {project}",
        }

    @pytest.mark.django_db
    def it_updates_existing_test(expect, client, payload):
        local_payload = payload.copy()
        local_payload["branch"] = ""
        local_payload["commit"] = ""
        response = post(client, url, local_payload)
        test = Test.objects.get()

        expect(response.status_code) == 201
        expect(response.json()) == {
            "project": "my-user › my-project",
            "test": "my feature › my test",
            "result": "passed",
        }
        expect(test.original_branch) == ""
        expect(test.original_commit) == ""

        response = post(client, url, payload)
        test.refresh_from_db()

        expect(response.status_code) == 200
        expect(test.original_branch) == "main"
        expect(test.original_commit) == "abc123"
