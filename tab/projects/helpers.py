from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import User

import log
from github import GithubException
from requests.exceptions import RequestException

from tab.core.models import Organization

if TYPE_CHECKING:
    from .models import Project


def insert_breaks(text: str) -> str:
    """Insert line-break opportunities for long test names."""
    return text.replace("_", "_<wbr>").replace("::", "::<wbr>")


def humanize_duration(value: float | None) -> str:
    """Format duration in seconds as XmXs when over a minute."""
    if value is None or value < 0:
        return "—"
    if value >= 100:  # 3 or more digits
        minutes = int(value // 60)
        seconds = int(value % 60)
        return f"{minutes}m{seconds}s"
    return f"{value:.1f}s"


def get_disabled_test_metrics(project: Project) -> dict[User, dict[str, int]]:
    """Compute statistics on disabled tests grouped by user."""

    # Get all tests that were ever disabled
    tests = project.tests.filter(disabled_user__isnull=False).select_related(
        "disabled_user"
    )

    # Group by user and current status
    data = {}
    for test in tests:
        user: User = test.disabled_user  # type: ignore[assignment]
        if user not in data:
            data[user] = {
                "total": 0,
                "disabled": 0,
                "enabled": 0,
            }

        data[user]["total"] += 1
        if test.disabled_at:
            data[user]["disabled"] += 1
        else:
            data[user]["enabled"] += 1

    return data


def rerun_failed_jobs(
    organization: Organization, project: Project, run_id: int
) -> str | None:
    assert "github.com" in project.repository, "Only GitHub is supported for now"
    github = organization.get_github_client()
    if not github:
        return None

    try:
        repo = github.get_repo(project.path)
        run = repo.get_workflow_run(run_id)
        status, _headers, body = run._requester.requestJson(
            "POST", f"{run.url}/rerun-failed-jobs"
        )
    except (GithubException, RequestException, OSError) as e:
        log.error(f"Unable to rerun failed jobs for {project.path} @ {run_id}: {e}")
        return None

    if status != 201:
        log.error(f"Unable to rerun failed jobs for {project.path} @ {run_id}: {body}")
        return None

    # GitHub Actions reuses the same run ID for subsequent attempts
    url = f"{project.repository}/actions/runs/{run_id}"
    log.info(f"Rerun failed jobs for {project.path} @ {run_id}: {url}")
    return url
