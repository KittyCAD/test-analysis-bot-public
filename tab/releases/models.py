from __future__ import annotations

from django.db import models
from django.utils import timezone

import log

from tab.api.helpers import update_status
from tab.core.models import Organization
from tab.projects.models import Project, Result

from .enums import Type
from .managers import EnvironmentManager


class Environment(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="environments"
    )

    url = models.URLField(null=True, blank=True)
    name = models.CharField(max_length=100, choices=Type.choices)

    dependencies = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name="dependents"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    objects: EnvironmentManager = EnvironmentManager()

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.get_name_display()}: {self.url or self.project}"

    def change(self, branch: str, commit: str) -> Release:
        release, created = Release.objects.get_or_create(
            environment=self, commit=commit, defaults=dict(branch=branch)
        )
        if created:
            log.info(f"Created release: {release}")
        else:
            log.info(f"Found release: {release}")
        return release


class Release(models.Model):
    environment = models.ForeignKey(
        Environment, on_delete=models.CASCADE, related_name="releases"
    )

    branch = models.CharField(max_length=500, default="", db_index=True)
    commit = models.CharField(max_length=100, default="", db_index=True)
    results = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    tested_at = models.DateTimeField(null=True, blank=True, db_index=True)
    finalized_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["environment", "commit"]

    def __str__(self):
        return f"{self.environment} › {self.branch}@{self.commit_humanized}"

    @property
    def branch_url(self) -> str:
        if not self.branch:
            return ""
        return f"{self.environment.project.repository}/tree/{self.branch}"

    @property
    def commit_humanized(self) -> str:
        return self.commit[:7]

    @property
    def commit_url(self) -> str:
        if not self.commit:
            return ""
        return f"{self.environment.project.repository}/commit/{self.commit}"

    def finalize(self):
        log.info(f"Finalizing release: {self}")

        project: Project = self.environment.project
        organization = Organization.objects.get(
            repository_index=project.repository_index
        )

        health = Result.objects.get_health(project, self.commit, final=True)
        update_status(organization, project, self.commit, self.branch, health)

        self.finalized_at = timezone.now()
        self.save()
