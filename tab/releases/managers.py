from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.db.models import Q
from django.utils import timezone

import log

from tab.projects.models import Project, Result

from .enums import Type

if TYPE_CHECKING:
    from tab.core.models import Organization

    from .models import Environment, Release


class EnvironmentManager(models.Manager):
    def filter_promotable(self, organization: Organization):
        return (
            self.filter(project__repository__startswith=organization.repository_index)
            .exclude(name=Type.LOCAL)
            .filter(~Q(name=Type.REVIEW) | Q(placeholder=True))
            .select_related("project")
            .prefetch_related("dependencies")
        )

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
            from .models import Release

            existing_release = (
                Release.objects.filter(
                    environment__project=project,
                    environment__name=Type.REVIEW,
                    branch=result.branch,
                    commit=result.commit,
                )
                .select_related("environment")
                .order_by("created_at")
                .first()
            )

            if url:
                environment, created = self.get_or_create(  # type: ignore[assignment]
                    project=project, url=url, name=Type.REVIEW
                )
                if (
                    existing_release
                    and existing_release.environment_id != environment.id
                ):
                    existing_release.environment = environment
                    existing_release.save(update_fields=["environment"])
            elif existing_release:
                environment = existing_release.environment
                created = False
            else:
                placeholder_url = None
                if environment := self.filter(
                    project=project,
                    name=Type.REVIEW,
                    placeholder=True,
                ).first():  # type: ignore[assignment]
                    placeholder_url = environment.url  # type: ignore[attr-defined]
                environment, created = self.get_or_create(  # type: ignore[assignment]
                    project=project, url=placeholder_url, name=Type.REVIEW
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
