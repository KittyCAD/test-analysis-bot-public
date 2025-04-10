import json

import log
from ninja import Router, Schema
from ninja.security import APIKeyHeader

from tab.projects.models import Project, Result, Test


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        # TODO: Implement authentication
        log.info(f"Authenticating with API key: {key}")
        return True


router = Router()
api_key = ApiKey()


class ResultSchema(Schema):
    project: str
    branch: str
    commit: str
    test: str
    status: str
    duration: float | None = None
    message: str | None = None

    @classmethod
    def get_metadata(cls, request_body: dict) -> dict:
        return {k: v for k, v in request_body.items() if k not in cls.model_fields}


class ErrorResponse(Schema):
    detail: str


@router.post(
    "/results",
    auth=api_key,
    response={
        # TODO: Define a schema for successful responses
        200: dict,
        201: dict,
        422: ErrorResponse,
    },
)
def results(request, payload: ResultSchema):
    try:
        project = Project.objects.from_repository(payload.project)
    except ValueError as e:
        return 422, {"detail": str(e)}

    test, created = Test.objects.get_or_create(
        project=project,
        name=payload.test,
        defaults=dict(
            original_branch=payload.branch,
            original_commit=payload.commit,
        ),
    )
    if created:
        status = 201
        log.info(f"Created test: {test}")
    elif test.update_origin(payload.branch, payload.commit):
        status = 200
        test.save()
        log.info(f"Updated test: {test}")
    else:
        status = 200
        log.info(f"Found test: {test}")

    metadata = ResultSchema.get_metadata(json.loads(request.body))
    result = Result.objects.create(
        test=test,
        status=payload.status,
        branch=payload.branch,
        commit=payload.commit,
        duration=payload.duration,
        message=payload.message,
        metadata=metadata,
    )

    return status, {
        "project": str(project),
        "test": str(test),
        "result": result.status,
    }
