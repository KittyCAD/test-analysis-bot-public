from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

import log

from .constants import ALL_BRANCHES, PENDING_THRESHOLD
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
        return results.select_related("suite", "test__project", "test__suite")

    def get_latest_commit(self, project: Project, branch: str) -> str | None:
        queryset = self.filter(test__project=project, branch=branch).order_by(
            "-created_at"
        )
        return queryset.values_list("commit", flat=True).first()

    def get_health(self, project: Project, commit: str | None) -> Health:
        assert "github.com" in project.repository, "Only GitHub is supported for now"
        if not commit:
            return Health(total=0, state="pending", description="no results")

        latest_commit = self.get_latest_commit(project, project.default_branch)
        latest_results = self.filter(
            test__project=project, commit=latest_commit, final=True
        )
        expected_passed = latest_results.filter(
            status__in=Status.merge_allowed()
        ).count()

        results = self.filter(test__project=project, commit=commit, final=True)
        passed_results = results.filter(status__in=Status.merge_allowed())
        failed_results = results.filter(status__in=Status.merge_blocked())
        total = results.count()
        passed = passed_results.count()
        failed = failed_results.count()

        if first_result := results.order_by("created_at").first():
            age = timezone.now() - first_result.created_at  # type: ignore[attr-defined]
        else:
            age = timedelta()
        log.info(
            f"Processed expected results for {project.path} @ {commit[:7]}: "
            f"{passed} of {expected_passed} passing, "
            f"started {round(age.total_seconds(), 2)} seconds ago"
        )
        if passed < expected_passed and age < PENDING_THRESHOLD:
            state = "pending"
        elif failed:
            state = "failure"
        else:
            state = "success"

        description = f"{passed} of {total} passing"
        if new_failed := sum(1 for r in failed_results if r.new_failure):  # type: ignore
            s = "" if new_failed == 1 else "s"
            description += f", {new_failed} new failure{s}"

        return Health(total=total, state=state, description=description)
