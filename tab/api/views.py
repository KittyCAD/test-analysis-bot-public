import json
import tomllib

from django.conf import settings
from django.shortcuts import redirect

import log
from github import Github
from ninja import NinjaAPI

from tab.core.models import Organization
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Test

from .schemas import (
    ApiKey,
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

    metadata = ResultRequest.get_metadata(json.loads(request.body))
    test, created = Test.objects.get_or_create(
        project=project,
        name=payload.test,
        defaults=dict(
            original_branch=payload.branch,
            original_commit=payload.commit,
            metadata=metadata,
        ),
    )
    if created:
        status = 201
        log.info(f"Created test: {test}")
    elif payload.branch and not test.original_branch:
        status = 200
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
    "/share",
    auth=api_key,
    response={
        200: ShareResponse,
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

    results = Result.objects.filter(
        test__project=project, commit=payload.commit, final=True
    )
    total = results.count()
    failed = results.filter(
        status__in=[Status.FAILED, Status.XPASSED, Status.ERROR]
    ).count()
    passed = total - failed

    assert "github.com" in project.repository, "Only GitHub is supported for now"
    github = Github(organization.repository_token)
    repo = github.get_repo(project.path)
    commit = repo.get_commit(payload.commit)
    commit.create_status(
        state="failure" if failed else "success",
        target_url=f"{settings.BASE_URL}/projects/{project.path}/results?branch={payload.branch}&show=fails",
        description=f"{passed} of {total} tests are passing",
        context="Test Analysis Bot",
    )

    return 200, ShareResponse(tests=total)
