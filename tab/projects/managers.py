from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from .enums import Status

if TYPE_CHECKING:
    from .models import Project


class ResultManager(models.Manager):
    def get_branch_health(
        self, project: Project, branch: str, commit: str
    ) -> tuple[int, str, str]:
        results = self.filter(test__project=project, commit=commit, final=True)

        total = results.count()
        failed_results = results.filter(
            status__in=[Status.FAILED, Status.XPASSED, Status.ERROR]
        )
        failed = failed_results.count()
        new_failed = failed_results.filter(test__failure_rate__lt=0.1).count()

        passed = total - failed

        assert "github.com" in project.repository, "Only GitHub is supported for now"
        state = "failure" if failed else "success"
        description = f"{passed} of {total} tests are passing"
        if new_failed:
            s = "" if new_failed == 1 else "s"
            description += f", {new_failed} new failure{s}"

        return total, state, description
