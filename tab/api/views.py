import json

from django.shortcuts import redirect

import log
from ninja import NinjaAPI

from tab.projects.models import Project, Result, Test

from .schemas import ApiKey, ErrorResponse, ResultRequest, ResultResponse

api = NinjaAPI()
api_key = ApiKey()


@api.get("/", include_in_schema=False)
def index(request):
    return redirect("/api/docs")


@api.post(
    "/results",
    auth=api_key,
    response={
        200: ResultResponse,
        201: ResultResponse,
        422: ErrorResponse,
    },
)
def results(request, payload: ResultRequest):
    try:
        project = Project.objects.from_repository(payload.project)
    except ValueError as e:
        return 422, {"detail": str(e)}

    test, created = Test.objects.get_or_create(
        project=project,
        name=payload.test,
        defaults=dict(
            original_branch=payload.branch,  # type: ignore[attr-defined]
            original_commit=payload.commit,  # type: ignore[attr-defined]
        ),
    )
    if created:
        status = 201
        log.info(f"Created test: {test}")
    elif test.update_origin(payload.branch, payload.commit):  # type: ignore[attr-defined]
        status = 200
        test.save()
        log.info(f"Updated test: {test}")
    else:
        status = 200
        log.info(f"Found test: {test}")

    metadata = ResultRequest.get_metadata(json.loads(request.body))
    result = Result.objects.create(
        test=test,
        status=payload.status,  # type: ignore[attr-defined]
        branch=payload.branch,  # type: ignore[attr-defined]
        commit=payload.commit,  # type: ignore[attr-defined]
        duration=payload.duration,  # type: ignore[attr-defined]
        message=payload.message,  # type: ignore[attr-defined]
        metadata=metadata,
    )
    log.info(f"Created result: {result}")

    return status, ResultResponse(
        project=str(project),
        test=str(test),
        result=result.status,
    )
