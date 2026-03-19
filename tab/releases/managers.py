from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

import log

from tab.projects.models import Project, Result

from .constants import PLACEHOLDER_CHARACTER
from .enums import Type

if TYPE_CHECKING:
    from .models import Environment, Release


class EnvironmentManager(models.Manager):
    def process(self, project: Project, url: str | None, results: list[Result]):
        result = results[0]

        environment: Environment
        if not result.branch:
            environment, created = self.get_or_create(  # type: ignore[assignment]
                project=project, name=Type.LOCAL
            )
        elif result.branch == project.default_branch:
            # TODO: Handle multiple environments using the same branch
            environments = self.filter(
                project=project, name__in=[Type.STAGING, Type.PRODUCTION]
            )
            if environments.count() == 1:
                environment = environments.first()  # type: ignore[assignment]
                created = False
            else:
                environment, created = self.get_or_create(  # type: ignore[assignment]
                    project=project, name=Type.STAGING
                )
        else:
            placeholder_url = None
            if url is None:
                if environment := self.filter(
                    project=project,
                    name=Type.REVIEW,
                    url__contains=PLACEHOLDER_CHARACTER,
                ).first():  # type: ignore[assignment]
                    placeholder_url = environment.url  # type: ignore[attr-defined]
            environment, created = self.get_or_create(  # type: ignore[assignment]
                project=project, url=url or placeholder_url, name=Type.REVIEW
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
