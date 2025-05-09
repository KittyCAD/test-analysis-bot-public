from django.conf import settings

import log
from github import Github, GithubException

from tab.core.models import Organization
from tab.projects.models import Project
from tab.projects.types import Health


def update_status(
    organization: Organization,
    project: Project,
    sha: str,
    branch: str,
    health: Health,
):
    assert "github.com" in project.repository, "Only GitHub is supported for now"

    if not organization.repository_token:
        log.warning(f"{organization} has no repository token")
        return

    github = Github(organization.repository_token)
    try:
        repo = github.get_repo(project.path)
        commit = repo.get_commit(sha)
    except GithubException as e:
        return 404, {"detail": str(e)}
    commit.create_status(
        state=health.state,
        target_url=f"{settings.BASE_URL}/projects/{project.path}/results?branch={branch}&show=fails",
        description=health.description,
        context="Test Analysis Bot",
    )
