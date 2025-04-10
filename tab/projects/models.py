from django.db import models

import log

from .constants import ANSI_ESCAPE


class ProjectManager(models.Manager):

    @staticmethod
    def clean_repository(value: str):
        return value.removesuffix(".git").strip("/")

    def from_repository(self, url: str):
        cleaned_url = self.clean_repository(url)
        if "://" not in cleaned_url or cleaned_url.count("/") < 4:
            raise ValueError(f"Invalid repository URL: {cleaned_url}")
        try:
            project = self.get(repository__iexact=cleaned_url)
            log.info(f"Found project: {project}")
        except Project.DoesNotExist:
            project = self.create(repository=cleaned_url)
            log.info(f"Created project: {project}")
        return project


class Project(models.Model):
    repository = models.URLField(unique=True)
    default_branch = models.CharField(max_length=100, default="main")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ProjectManager = ProjectManager()

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        self._update_repository()
        parts = self.repository.split("/")
        return " › ".join(parts[3:])

    def save(self, *args, **kwargs):
        self._update_repository()
        super().save(*args, **kwargs)

    def _update_repository(self):
        self.repository = ProjectManager.clean_repository(self.repository)


class Test(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    name = models.CharField(max_length=1000)
    original_branch = models.CharField(max_length=100, default="")
    original_commit = models.CharField(max_length=100, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def update_origin(self, branch: str, commit: str) -> bool:
        updated = False
        if not all([self.original_branch, self.original_commit]) and any(
            [branch, commit]
        ):
            self.original_branch = self.original_branch or branch
            self.original_commit = self.original_commit or commit
            updated = True
        return updated


class Status(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"

    TIMED_OUT = "timedOut", "Timed Out"
    INTERRUPTED = "interrupted", "Interrupted"


class Result(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=Status.choices)
    branch = models.CharField(max_length=100, default="")
    commit = models.CharField(max_length=100, default="")
    duration = models.FloatField(null=True)
    message = models.TextField(null=True)
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return Status(self.status).label

    def save(self, *args, **kwargs):
        if self.duration:
            self.duration = round(self.duration, 3)
        if self.message:
            self.message = ANSI_ESCAPE.sub("", self.message)
        super().save(*args, **kwargs)
