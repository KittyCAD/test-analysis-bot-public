from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

import log

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
        release.results += len(results)
        release.tested_at = timezone.now()
        release.save()

        return environment
