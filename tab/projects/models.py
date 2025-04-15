from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property

import log

from .constants import ANSI_ESCAPE, RELEVANT_SAMPLES, get_default_branches
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
    default_branches = models.JSONField(default=get_default_branches)
    error_indicators = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ProjectManager = ProjectManager()

    def __str__(self):
        return self.name

    @property
    def path(self) -> str:
        self._update_repository()
        parts = self.repository.split("/")
        return "/".join(parts[3:])

    @property
    def name(self) -> str:
        return self.path.replace("/", " › ")

    @property
    def default_branch(self) -> str:
        return self.default_branches[0]

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

    enabled = models.BooleanField(default=False)
    failure_rate = models.FloatField(default=-1)
    average_duration = models.FloatField(default=-1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def failure_rate_humanized(self) -> str:
        if self.failure_rate < 0:
            return "—"
        return f"{self.failure_rate*100:.1f}%"

    @property
    def average_duration_humanized(self) -> str:
        if self.average_duration < 0:
            return "—"
        return f"{self.average_duration:.1f}s"

    @cached_property
    def relevant_branches(self) -> list[str]:
        branches = self.project.default_branches
        if self.original_branch:
            branches.insert(0, self.original_branch)
        if settings.DEBUG:
            branches.insert(0, "")  # unknown local branch
        return branches

    @cached_property
    def last_result(self) -> Result:
        result = (
            self.result_set.filter(branch__in=self.relevant_branches)
            .order_by("-created_at")
            .first()
        )
        assert result is not None, f"Test has no results: {self}"
        return result

    @cached_property
    def markers(self) -> list[str]:
        metadata = self.last_result.metadata
        # TODO: Consider making 'annotations' and/or 'tags' a proper field
        return metadata.get("annotations", []) + metadata.get("tags", [])

    def update_enabled(self) -> bool:
        old = self.enabled
        result = (
            self.result_set.filter(branch=self.project.default_branch)
            .order_by("-created_at")
            .first()
        )

        new = bool(result and result.status != Status.SKIPPED)
        if old == new:
            return False

        log.debug(f"Test has new enabled status: {old} => {new}")
        self.enabled = new
        return True

    def update_failure_rate(self) -> bool:
        old = self.failure_rate
        results = Result.objects.filter(
            test=self,
            branch__in=self.relevant_branches,
            status__in=[
                Status.PASSED,
                Status.FAILED,
                Status.SKIPPED,
                Status.XFAILED,
                Status.XPASSED,
            ],
        ).order_by("-created_at")[:RELEVANT_SAMPLES]
        if not results:
            return False

        failed = sum(
            1 for result in results if result.status in [Status.FAILED, Status.XPASSED]
        )
        new = round(failed / len(results), 3)

        if old == new:
            return False

        log.debug(f"Test has new failure rate: {old*100}% => {new*100}%")
        self.failure_rate = new
        return True

    def update_average_duration(self) -> bool:
        old = self.average_duration
        results = Result.objects.filter(
            test=self,
            branch__in=self.relevant_branches,
            status__in=[Status.PASSED, Status.FAILED, Status.XPASSED, Status.XFAILED],
            duration__gt=0,
        ).order_by("-created_at")[:RELEVANT_SAMPLES]

        durations = [result.duration for result in results if result.duration]
        if not durations:
            return False

        new = round(sum(durations) / len(durations), 1)
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

    @property
    def duration_humanized(self) -> str:
        if self.duration is None or self.duration < 0:
            return "—"
        return f"{self.duration:.1f}s"

    def save(self, *args, **kwargs):
        self.status = Status.normalize(
            self.status,
            # TODO: Consider making 'annotations' a proper field
            annotations=self.metadata.get("annotations", []),
            message=self.message,
            error_indicators=self.test.project.error_indicators,
        )
        if self.duration:
            self.duration = round(self.duration, 3)
        if self.message:
            self.message = ANSI_ESCAPE.sub("", self.message)
        if self.target:
            self.target = Target.normalize(self.target)
        if self.platform:
            self.platform = Platform.normalize(self.platform)

        super().save(*args, **kwargs)

        if (
            self.test.update_enabled()
            or self.test.update_failure_rate()
            or self.test.update_average_duration()
        ):
            self.test.save()
