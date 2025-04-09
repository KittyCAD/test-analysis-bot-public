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
    log.info(f"{response.status_code} response: {response.json()}")
    return response


@pytest.mark.django_db
def describe_results():

    url = "/api/results"

    def it_creates_projects_automatically(expect, client):
        data = {
            "repository": "https://github.com/my-user/my-project",
        }
        response = post(client, url, data)

        expect(response.status_code) == 200
        expect(response.json()) == {"project": "my-user / my-project"}

    def it_rejects_invalid_repositories(expect, client):
        data = {
            "repository": "https://github.com/my-user",
        }
        response = post(client, url, data)

        expect(response.status_code) == 422
        expect(response.json()) == {
            "detail": "Invalid repository: https://github.com/my-user"
        }
