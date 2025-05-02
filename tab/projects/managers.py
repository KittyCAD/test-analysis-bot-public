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
        failed = results.filter(
            status__in=[Status.FAILED, Status.XPASSED, Status.ERROR]
        ).count()
        passed = total - failed

        assert "github.com" in project.repository, "Only GitHub is supported for now"
        state = "failure" if failed else "success"
        description = f"{passed} of {total} tests are passing"

        return total, state, description
