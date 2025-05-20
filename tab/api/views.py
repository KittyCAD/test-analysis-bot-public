import json
import tomllib

from django.conf import settings
from django.shortcuts import redirect

import log
from ninja import Form, NinjaAPI

from tab.core.models import Organization
from tab.projects.models import Project, Result, Suite, Test

from .helpers import parse_junit_xml, update_status
from .schemas import (
    ApiKey,
    BulkResultRequest,
    BulkResultResponse,
    ErrorResponse,
    ResultRequest,
    ResultResponse,
    ShareRequest,
    ShareResponse,
)

project = tomllib.load(open("pyproject.toml", "rb"))["project"]
api = NinjaAPI(
    title="Test Analysis Bot",
    version=project["version"],
    description=project["description"],
)
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
    tags=["Tests"],
)
def results(request, payload: ResultRequest):
    assert hasattr(payload, "branch") and hasattr(payload, "commit")  # type hint

    try:
        if hasattr(settings, "TEST"):
            log.warning("Skipping ownership check for tests")
            project = Project.objects.from_repository(payload.project)
        else:
            key = request.headers.get(ApiKey.param_name)
            organization = Organization.objects.get(key=key)
            project = Project.objects.from_repository(
                payload.project, organization.repository_index
            )
    except ValueError as e:
        return 422, {"detail": str(e)}

    suite, created = Suite.objects.get_or_create(project=project, name=payload.suite)
    if created:
        log.info(f"Created suite: {suite}")
    else:
        log.info(f"Found suite: {suite}")

    metadata = ResultRequest.get_metadata(json.loads(request.body))
    test, created = Test.objects.get_or_create(
        project=project,
        name=payload.test,
        defaults=dict(
            suite=suite,
            original_branch=payload.branch,
            original_commit=payload.commit,
            metadata=metadata,
        ),
    )
    if created:
        status = 201
        log.info(f"Created test: {test}")
    elif (test.suite != suite) or (payload.branch and not test.original_branch):
        status = 200
        test.suite = suite
        test.original_branch = test.original_branch or payload.branch
        test.original_commit = test.original_commit or payload.commit
        test.metadata = test.metadata or metadata
        test.save()
        log.info(f"Updated test: {test}")
    else:
        status = 200
        log.info(f"Found test: {test}")

    result = Result.objects.create(
        test=test,
        **payload.get_model_fields(),
        metadata=metadata,
    )
    log.info(f"Created result: {result}")

    return status, ResultResponse(
        project=str(project),
        test=str(test),
        status=result.status,
        block=result.block,
    )


@api.post(
    "/results/bulk",
    auth=api_key,
    response={
        200: BulkResultResponse,
        422: ErrorResponse,
    },
    tags=["Tests"],
)
def bulk_results(request, payload: Form[BulkResultRequest]):
    try:
        if hasattr(settings, "TEST"):
            log.warning("Skipping ownership check for tests")
            project = Project.objects.from_repository(payload.project)
        else:
            key = request.headers.get(ApiKey.param_name)
            organization = Organization.objects.get(key=key)
            project = Project.objects.from_repository(
                payload.project, organization.repository_index
            )
    except ValueError as e:
        return 422, {"detail": str(e)}

    if tests := request.FILES.get("tests"):
        content = tests.read().decode("utf-8")
        metadata = BulkResultRequest.get_metadata(request.POST.dict())
        count = parse_junit_xml(
            content, project, payload.branch, payload.commit, metadata
        )
        response = BulkResultResponse(
            project=str(project),
            branch=payload.branch,
            commit=payload.commit,
            tests=count,
        )
        return 200, response.dict()

    return 422, {"detail": "Include 'tests' as a JUnit XML file upload."}


@api.post(
    "/share",
    auth=api_key,
    response={
        200: ShareResponse,
        404: ErrorResponse,
        422: ErrorResponse,
    },
    tags=["Tests"],
)
def share(request, payload: ShareRequest):
    try:
        key = request.headers.get(ApiKey.param_name)
        organization = Organization.objects.get(key=key)
        project = Project.objects.from_repository(
            payload.project, organization.repository_index
        )
    except (Organization.DoesNotExist, ValueError) as e:
        return 422, {"detail": str(e)}

    health = Result.objects.get_health(project, payload.commit)
    update_status(organization, project, payload.commit, payload.branch, health)

    return 200, ShareResponse(
        project=str(project),
        branch=payload.branch,
        commit=payload.commit,
        tests=health.total,
    )
