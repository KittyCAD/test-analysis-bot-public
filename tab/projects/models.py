import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

import log

from .constants import ANSI_ESCAPE, SAMPLE_COUNT, get_default_branches
from .enums import Platform, Status, Target
from .managers import ProjectManager, ResultManager


class Project(models.Model):
    repository = models.URLField(unique=True, db_index=True)
    default_branches = models.JSONField(default=get_default_branches)
    error_indicators = models.JSONField(default=list, blank=True)

    branch_inactive_threshold = models.DurationField(
        default=timedelta(days=7),
        help_text="Branches older than this will be hidden by default",
    )
    test_inactive_threshold = models.DurationField(
        default=timedelta(days=7),
        help_text="Tests with no results this recent time will be hidden by default",
    )
    test_stale_threshold = models.DurationField(
        default=timedelta(days=30),
        help_text="Tests with no results this recent time will be pruned automatically",
    )
    result_stale_threshold = models.DurationField(
        default=timedelta(days=7),
        help_text="Branch results older than this will be pruned automatically",
    )

    cleaned_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tests")

    name = models.CharField(max_length=1000, db_index=True)
    original_branch = models.CharField(max_length=100, default="")
    original_commit = models.CharField(max_length=100, default="")
    metadata = models.JSONField(default=dict, blank=True)

    disabled = models.BooleanField(
        default=False, help_text="Forces the test to be disabled", db_index=True
    )
    disabled_platforms = models.JSONField(
        default=list,
        blank=True,
        help_text="Platforms to limit the disabled override",
    )
    disabled_reason = models.TextField(
        default="",
        blank=True,
        help_text="Explanation of why the test is temporarily disabled",
    )
    disabled_tracker = models.URLField(
        null=True,
        blank=True,
        help_text="URL of the ticket tracking the work to restore the test",
    )
    disabled_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who disabled the test",
    )

    enabled = models.BooleanField(
        default=False,
        editable=False,
        help_text="Test is allowed to block merges and releases",
        db_index=True,
    )
    failure_rate = models.FloatField(
        default=-1,
        editable=False,
        help_text="Total failure rate on significant branches including reruns",
    )
    block_rate = models.FloatField(
        default=-1,
        editable=False,
        help_text="Effective failure rate with reruns and ignored failures excluded",
    )
    average_duration = models.FloatField(
        default=-1,
        editable=False,
    )
    last_result = models.ForeignKey(
        "Result", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "name"]),
            models.Index(fields=["project", "disabled"]),
            models.Index(fields=["project", "enabled"]),
        ]

    def __str__(self):
        return self.name

    @property
    def regex(self) -> str:
        label = self.name.split(" › ")[-1]
        return re.escape(label).replace(r"\ ", " ").replace("'", r"'\''")

    @property
    def failure_rate_help(self) -> str:
        return self._meta.get_field("failure_rate").help_text  # type: ignore

    @property
    def block_rate_help(self) -> str:
        return self._meta.get_field("block_rate").help_text  # type: ignore

    @property
    def enabled_help(self) -> str:
        return self._meta.get_field("enabled").help_text  # type: ignore

    @property
    def failure_rate_humanized(self) -> str:
        if self.failure_rate < 0:
            return "—"
        return f"{self.failure_rate:.0%}"

    @property
    def block_rate_humanized(self) -> str:
        if self.block_rate < 0:
            return "—"
        return f"{self.block_rate:.0%}"

    @property
    def average_duration_humanized(self) -> str:
        if self.average_duration < 0:
            return "—"
        return f"{self.average_duration:.1f}s"

    @property
    def significant_branches(self) -> list[str]:
        branches = list(self.project.default_branches)
        if self.original_branch and self.original_branch not in branches:
            branches.insert(0, self.original_branch)
        if settings.DEBUG:
            branches.insert(0, "")  # unknown local branch
        return branches

    @property
    def show_advanced_options(self) -> bool:
        return bool(self.last_result) and self.failure_rate > 0.25

    @property
    def markers(self) -> list[str]:
        metadata = self.last_result.metadata if self.last_result else {}
        # TODO: Consider making 'annotations' and/or 'tags' a proper field
        values = metadata.get("annotations", []) + metadata.get("tags", [])
        if self.disabled:
            values.append("disabled")
        return values

    def update_failure_rate(self) -> bool:
        old = self.failure_rate
        results = self.results.filter(
            branch__in=self.significant_branches,
        ).order_by("-created_at")
        if not results.exists():
            return False

        results = results[:SAMPLE_COUNT]
        failed = sum(
            result.status
            in {Status.FAILED, Status.XPASSED, Status.ERROR, Status.DISABLED}
            for result in results
        )
        new = round(failed / len(results), 6)

        if old == new:
            return False

        log.debug(f"Test has new failure rate: {old:.3%} => {new:.3%}")
        self.failure_rate = new
        return True

    def update_block_rate(self) -> bool:
        old = self.block_rate
        results = self.results.filter(
            branch__in=self.significant_branches,
            final=True,
        ).order_by("-created_at")
        if not results.exists():
            return False

        results = results[:SAMPLE_COUNT]
        failed = sum(
            result.status in {Status.FAILED, Status.XPASSED, Status.ERROR}
            for result in results
        )
        new = round(failed / len(results), 6)

        if old == new:
            return False

        log.debug(f"Test has new block rate: {old:.3%} => {new:.3%}")
        self.block_rate = new
        return True

    def update_average_duration(self) -> bool:
        old = self.average_duration
        results = self.results.filter(
            branch__in=self.significant_branches,
            status__in=[
                Status.PASSED,
                Status.FAILED,
                Status.XPASSED,
                Status.XFAILED,
                Status.DISABLED,
            ],
            duration__gt=0,
        ).order_by("-created_at")
        if not results.exists():
            return False

        results = results[:SAMPLE_COUNT]
        durations = [result.duration for result in results if result.duration]
        if not durations:
            return False

        new = round(sum(durations) / len(durations), 3)
        if old == new:
            return False

        log.debug(f"Test has new average duration: {old} => {new} seconds")
        self.average_duration = new
        return True

    def update(self) -> bool:
        return any(
            [
                self.update_failure_rate(),
                self.update_block_rate(),
                self.update_average_duration(),
            ]
        )

    def save(self, *args, **kwargs):
        if self.pk:
            self.last_result = (
                self.results.filter(branch=self.project.default_branch)
                .order_by("-created_at")
                .first()
            )
        if self.disabled_platforms:
            self.disabled = True
        self.enabled = bool(
            not self.disabled
            and self.last_result
            and self.last_result.status not in {Status.SKIPPED, Status.DISABLED}
        )
        super().save(*args, **kwargs)


class Result(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")

    branch = models.CharField(max_length=100, default="", db_index=True)
    commit = models.CharField(max_length=100, default="", db_index=True)
    target = models.CharField(
        max_length=100, null=True, choices=Target.choices, db_index=True
    )
    platform = models.CharField(
        max_length=100, null=True, choices=Platform.choices, db_index=True
    )
    final = models.BooleanField(
        default=True, help_text="Indicates this was the final retry", db_index=True
    )

    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    duration = models.FloatField(null=True)
    message = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects: ResultManager = ResultManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["test", "branch", "commit"]),
            models.Index(fields=["test", "branch", "created_at"]),
            models.Index(fields=["test", "status", "final"]),
        ]

    def __str__(self):
        status = Status(self.status).label
        duration = self.duration_humanized if self.duration else "???s"
        branch = self.branch or "???"
        commit = self.commit_humanized if self.commit else "???"
        return f"{status} after {duration} on {branch!r} at {commit}"

    @property
    def branch_url(self) -> str:
        if not self.branch:
            return ""
        return f"{self.test.project.repository}/tree/{self.branch}"

    @property
    def merge_url(self) -> str:
        if number := self.metadata.get("CI_PR_NUMBER"):  # GitHub
            return f"{self.test.project.repository}/pull/{number}"
        if number := self.metadata.get("CI_MERGE_REQUEST_IID"):  # GitLab
            return f"{self.test.project.repository}/-/merge_requests/{number}"
        return ""

    @property
    def commit_humanized(self) -> str:
        if not self.commit:
            return ""
        return self.commit[:7]

    @property
    def commit_url(self) -> str:
        if not self.commit:
            return ""
        return f"{self.test.project.repository}/commit/{self.commit}"

    @property
    def block(self) -> bool:
        return self.status in {
            Status.FAILED,
            Status.XPASSED,
            Status.ERROR,
            Status.TIMEDOUT,
        }

    @property
    def duration_humanized(self) -> str:
        if self.duration is None or self.duration < 0:
            return "—"
        return f"{self.duration:.1f}s"

    @property
    def markers(self) -> list[str]:
        metadata = self.metadata
        # TODO: Consider making 'annotations' and/or 'tags' a proper field
        values = metadata.get("annotations", []) + metadata.get("tags", [])
        if self.test.disabled_platforms:
            if self.platform in self.test.disabled_platforms:
                values.append("disabled")
        elif self.test.disabled:
            values.append("disabled")
        return values

    @property
    def originated_from_branch(self) -> bool:
        return (
            self.branch == self.test.original_branch
            and self.branch not in self.test.project.default_branches
        )

    def save(self, *args, **kwargs):
        if self.duration:
            self.duration = round(self.duration, 3)
        if self.message:
            self.message = ANSI_ESCAPE.sub("", self.message)
        if self.target:
            self.target = Target.normalize(self.target)
        if self.platform:
            self.platform = Platform.normalize(self.platform)
        self.status = Status.normalize(
            self.status,
            markers=self.markers,
            message=self.message,
            error_indicators=self.test.project.error_indicators,
        )

        super().save(*args, **kwargs)

        if self.final:
            if results := Result.objects.filter(
                test=self.test,
                commit=self.commit,
                target=self.target,
                platform=self.platform,
                final=True,
                created_at__lt=self.created_at,
            ).exclude(id=self.id):
                results.update(final=False)
                for result in results:
                    log.info(f"Demoted result: {result}")

        self.test.update()
        self.test.save()
