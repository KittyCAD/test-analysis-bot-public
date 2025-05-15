from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

import log

from .constants import ALL_BRANCHES
from .enums import Status
from .types import Health

if TYPE_CHECKING:
    from .models import Project, Test


class ProjectManager(models.Manager):

    @staticmethod
    def clean_repository(value: str):
        return value.removesuffix(".git").strip("/")

    def from_repository(self, project_url: str, organization_url: str = ""):
        project_url = self.clean_repository(project_url)

        if "://" not in project_url or project_url.count("/") < 4:
            raise ValueError(f"Invalid repository URL: {project_url}")

        if organization_url and not project_url.startswith(organization_url + "/"):
            raise ValueError(f"Repository not part of your organization: {project_url}")

        try:
            project = self.get(repository__iexact=project_url)
            log.info(f"Found project: {project}")
        except ObjectDoesNotExist:
            project = self.create(repository=project_url)
            log.info(f"Created project: {project}")

        return project


class ResultManager(models.Manager):
    def filter_with_default_branches(self, test: Test, branch: str | None):
        if branch == ALL_BRANCHES:
            results = self.filter(test=test)
        elif branch:
            branches = [branch] + test.significant_branches
            results = self.filter(test=test, branch__in=branches)
        else:
            results = self.filter(test=test, branch__in=test.significant_branches)
        return results.select_related("test__project")

    def get_latest_commit(self, project: Project, branch: str) -> str:
        queryset = self.filter(test__project=project, branch=branch).order_by(
            "-created_at"
        )
        return queryset.values_list("commit", flat=True).first()

    def get_health(self, project: Project, commit: str) -> Health:
        latest_commit = self.get_latest_commit(project, project.default_branch)
        latest_results = self.filter(
            test__project=project, commit=latest_commit, final=True
        )
        expected = latest_results.count()
        expected_passed = latest_results.filter(status=Status.PASSED).count()

        results = self.filter(test__project=project, commit=commit, final=True)
        total = results.count()
        failed_results = results.filter(
            status__in=[Status.FAILED, Status.XPASSED, Status.ERROR]
        )
        failed = failed_results.count()
        passed = total - failed

        log.info(
            f"Processed results for {project} @ {commit}: "
            f"{total} of {expected} expected total, "
            f"{passed} of {expected_passed} expected passing"
        )
        assert "github.com" in project.repository, "Only GitHub is supported for now"
        if total < expected * 0.95 and passed < expected_passed * 0.95:
            state = "pending"
        elif failed:
            state = "failure"
        else:
            state = "success"

        description = f"{passed} of {total} passing"
        if new_failed := failed_results.filter(test__failure_rate__lt=0.1).count():
            s = "" if new_failed == 1 else "s"
            description += f", {new_failed} new failure{s}"

        return Health(total=total, state=state, description=description)
