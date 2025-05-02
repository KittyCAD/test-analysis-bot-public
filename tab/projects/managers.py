from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

import log

from .enums import Status
from .types import Health

if TYPE_CHECKING:
    from .models import Project


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
    def get_latest_commit(self, project: Project, branch: str) -> str:
        queryset = self.filter(test__project=project, branch=branch).select_related(
            "test", "test__project"
        )
        return queryset.values_list("commit", flat=True).first()

    def get_health(self, project: Project, commit: str) -> Health:
        results = self.filter(test__project=project, commit=commit, final=True)
        total = results.count()
        failed_results = results.filter(
            status__in=[Status.FAILED, Status.XPASSED, Status.ERROR]
        )
        failed = failed_results.count()
        passed = total - failed

        assert "github.com" in project.repository, "Only GitHub is supported for now"
        expected = project.tests.filter(
            updated_at__gte=timezone.now() - project.test_inactive_threshold
        ).count()
        if total < expected / 2:
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
