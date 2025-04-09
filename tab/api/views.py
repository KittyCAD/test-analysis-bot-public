import json

import log
from ninja import Router, Schema
from ninja.security import HttpBearer
from pydantic import HttpUrl

from tab.projects.models import Project, Test

router = Router()


class Result(Schema):
    project: str
    test: str


class ErrorResponse(Schema):
    detail: str


class AuthBearer(HttpBearer):
    def authenticate(self, request, token: str):
        # TODO: Implement authentication
        log.info(f"Authenticating with token: {token}")
        return True


@router.post("/results", auth=AuthBearer(), response={200: dict, 422: ErrorResponse})
def results(request, result: Result):
    try:
        project = Project.objects.from_repository(result.project)
    except ValueError as e:
        return 422, {"detail": str(e)}

    test, created = Test.objects.get_or_create(project=project, name=result.test)
    if created:
        log.info(f"Created test: {test}")
    else:
        log.info(f"Found test: {test}")

    extra = {
        k: v
        for k, v in json.loads(request.body).items()
        if k not in Result.model_fields
    }
    log.info(f"Extra parameters: {json.dumps(extra, indent=2)}")

    return {
        "project": str(project),
        "test": str(test),
    }
