import json

from django.shortcuts import get_object_or_404, redirect

import log
from ninja import Router, Schema
from ninja.security import HttpBearer
from pydantic import HttpUrl

from tab.projects.models import Project

router = Router()


class Result(Schema):
    repository: HttpUrl


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
        project = Project.objects.from_repository(str(result.repository))
    except ValueError as e:
        return 422, {"detail": str(e)}

    extra = {
        k: v
        for k, v in json.loads(request.body).items()
        if k not in Result.model_fields
    }
    log.info(f"Extra parameters: {extra}")

    return {"project": str(project)}
