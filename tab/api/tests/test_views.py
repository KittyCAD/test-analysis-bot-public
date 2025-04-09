import json

import log
import pytest


def post(client, url: str, data: dict):
    log.info(f"POST {url}: {data}")
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={
            "Authorization": "Bearer my-token",
        },
    )
    try:
        log.info(f"{response.status_code} response: {response.json()}")
    except ValueError:
        log.info(f"{response.status_code} response: {response.text}")
    return response


def describe_results():

    url = "/api/results"

    @pytest.mark.django_db
    def it_creates_projects_and_tests_automatically(expect, client):
        data = {
            "project": "https://github.com/my-user/my-project",
            "test": "my test",
        }
        response = post(client, url, data)

        expect(response.status_code) == 200
        expect(response.json()) == {
            "project": "my-user / my-project",
            "test": "my test",
        }

    @pytest.mark.parametrize(
        "project",
        [
            "https://github.com/my-user",
            "github.com/my-user/my-project",
            "my-user/my-project",
        ],
    )
    def it_rejects_invalid_repositories(expect, client, project):
        data = {
            "project": project,
            "test": "my test",
        }
        response = post(client, url, data)

        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": f"Invalid repository URL: {project}",
        }
