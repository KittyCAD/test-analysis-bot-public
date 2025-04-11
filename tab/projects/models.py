from django.db import models

import log

from .constants import ANSI_ESCAPE
from .enums import Platform, Status, Target


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
        except Project.DoesNotExist:
            project = self.create(repository=project_url)
            log.info(f"Created project: {project}")

        return project


class Project(models.Model):
    repository = models.URLField(unique=True)
    default_branches = models.JSONField(default=["main"])

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
    metadata = models.JSONField(default=dict)

    average_duration = models.FloatField(default=-1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def update_average_duration(self, *, samples: int = 100) -> bool:
        old = self.average_duration

        results = Result.objects.filter(
            test=self,
            branch__in=self.project.default_branches,
            duration__gt=0,
            status__in=[Status.PASSED, Status.FAILED],
        ).order_by("-created_at")[:samples]

        durations = [result.duration for result in results if result.duration]
        if not durations:
            return False

        new = round(sum(durations) / len(durations), 3)
        if old == new:
            return False

        log.debug(f"Test has new average duration: {old} => {new} seconds")
        self.average_duration = new
        return True


class Result(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=Status.choices)
    branch = models.CharField(max_length=100, default="")
    commit = models.CharField(max_length=100, default="")

    duration = models.FloatField(null=True)
    message = models.TextField(null=True)
    target = models.CharField(max_length=100, null=True, choices=Target.choices)
    platform = models.CharField(max_length=100, null=True, choices=Platform.choices)
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        branch = self.branch or "???"
        return f"{Status(self.status).label} after {self.duration or '???'} seconds on {branch!r}"

    def save(self, *args, **kwargs):
        if self.duration:
            self.duration = round(self.duration, 3)
        if self.message:
            self.message = ANSI_ESCAPE.sub("", self.message)
        if self.target:
            self.target = Target.normalize(self.target)
        if self.platform:
            self.platform = Platform.normalize(self.platform)

        super().save(*args, **kwargs)

        if self.duration:
            if self.test.update_average_duration():
                self.test.save()
