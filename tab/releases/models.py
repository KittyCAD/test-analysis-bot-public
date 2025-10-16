from __future__ import annotations

from django.db import models

import log

from tab.projects.models import Project

from .enums import Type
from .managers import EnvironmentManager


class Environment(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="environments"
    )

    url = models.URLField(null=True, blank=True)
    name = models.CharField(max_length=100, choices=Type.choices)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    objects: EnvironmentManager = EnvironmentManager()

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.get_name_display()}: {self.url or '???'}"

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
    results_passed = models.IntegerField(default=0)
    results_total = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    tested_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.environment} › {self.branch}@{self.commit}"
