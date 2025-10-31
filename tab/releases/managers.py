from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

import log

from tab.projects.enums import Status
from tab.projects.models import Project, Result

from .enums import Type

if TYPE_CHECKING:
    from .models import Environment, Release


class EnvironmentManager(models.Manager):
    def process(self, project: Project, results: list[Result]):
        result = results[0]

        environment: Environment
        if not result.branch:
            environment, created = self.get_or_create(  # type: ignore[assignment]
                project=project, name=Type.LOCAL
            )
        elif result.branch == project.default_branch:
            # TODO: Handle multiple environments using the same branch
            environment, created = self.get_or_create(  # type: ignore[assignment]
                project=project, name=Type.STAGING
            )
        else:
            environment, created = self.get_or_create(  # type: ignore[assignment]
                project=project, name=Type.PREVIEW
            )
        if created:
            log.info(f"Created environment: {environment}")
        else:
            log.info(f"Found environment: {environment}")

        release: Release = environment.change(result.branch, result.commit)
        if not release.tested_at:
            release.results_passed += sum(
                result.status not in Status.test_failed() for result in results
            )
            release.results_total += len(results)
            release.save()

        # TODO: Mark release as tested once both counts are >= last run

        return environment
