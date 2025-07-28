import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

import log

from .constants import (
    ANSI_ESCAPE,
    CHECKOUT_COMMAND,
    DEFAULT_SUITE,
    get_default_branches,
)
from .enums import Platform, Status, Target
from .managers import ProjectManager, ResultManager


class Project(models.Model):
    repository = models.URLField(unique=True, db_index=True)
    default_branches = models.JSONField(
        default=get_default_branches,
        help_text="Results from these branches will be considered in computed metrics",
    )
    sample_count = models.IntegerField(
        default=100,
        help_text="Number of recent test results to consider in computed metrics",
    )
    error_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Message fragments that indicate there was a setup error rather than failure",
    )
    skipped_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Message fragments that indicate a passed test was not actually able to run",
    )

    branch_inactive_threshold = models.DurationField(
        default=timedelta(days=7),
        help_text="Branches older than this will be hidden by default",
    )
    test_inactive_threshold = models.DurationField(
        default=timedelta(days=7),
        help_text="Tests with no results this recent will be hidden by default",
    )
    test_stale_threshold = models.DurationField(
        default=timedelta(days=30),
        help_text="Tests with no results this recent will be pruned automatically",
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


class Suite(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="suites"
    )
    name = models.CharField(max_length=100, db_index=True)

    supports_override = models.BooleanField(
        default=False,
        help_text="Indicates the suite is configured to allow disabling tests",
    )
    local_command = models.TextField(
        default="",
        blank=True,
        help_text="Pattern to run individual tests locally",
    )
    error_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Message fragments that indicate there was a setup error rather than failure",
    )
    skipped_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Message fragments that indicate a passed test was not actually able to run",
    )

    failure_rate_upper_threshold = models.FloatField(
        default=0.5, help_text="Upper threshold to consider unacceptable"
    )
    failure_rate_lower_threshold = models.FloatField(
        default=0.1, help_text="Lower threshold to consider acceptable"
    )
    block_rate_upper_threshold = models.FloatField(
        default=0.25, help_text="Upper threshold to consider unacceptable"
    )
    block_rate_lower_threshold = models.FloatField(
        default=0.05, help_text="Lower threshold to consider acceptable"
    )
    average_duration_upper_threshold = models.FloatField(
        default=60, help_text="Upper threshold to consider unacceptable"
    )
    average_duration_lower_threshold = models.FloatField(
        default=30, help_text="Lower threshold to consider acceptable"
    )

    tests_count = models.IntegerField(default=-1, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        if self.name == DEFAULT_SUITE:
            return str(self.project)
        return f"{self.project} › {self.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            self.tests_count = self.tests.count()
        super().save(*args, **kwargs)


class Test(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tests")
    suite = models.ForeignKey(
        Suite, null=True, blank=True, on_delete=models.SET_NULL, related_name="tests"
    )

    name = models.CharField(max_length=1000, db_index=True)
    original_branch = models.CharField(
        max_length=500,
        default="",
        help_text="Name of the branch that originally added this test",
    )
    original_commit = models.CharField(
        max_length=100,
        default="",
        help_text="Hash of the commit that originally added this test",
    )
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
        db_index=True,
    )
    disabled_tracker = models.URLField(
        null=True,
        blank=True,
        help_text="URL of the ticket tracking the work to restore the test",
        db_index=True,
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
        help_text="Seconds duration from recent runs on significant branches",
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
        if self.suite and self.suite.name != DEFAULT_SUITE:
            return f"{self.suite.name} › {self.name}"
        return self.name

    @property
    def regex(self) -> str:
        parts = self.name.split(" › ")

        # Remove file path prefix
        if "." in parts[0]:
            parts = parts[1:]

        # Remove entire prefix for fully-namespaced tests
        if "::" in parts[-1]:
            parts = [parts[-1]]

        # Join nested description blocks
        escaped_parts = [re.escape(part) for part in parts]
        label = ".*".join(escaped_parts)

        return (
            label.replace(r"\ ", " ")  # remove excessive escaping of spaces
            .replace("'", r"'\''")
            .replace(" > ", " ")  # fix for vitest pattern matching
            .replace('"', ".")  # replace quote marks for better shell support
            .strip()
        )

    @property
    def significant_branches(self) -> list[str]:
        branches = list(self.project.default_branches)
        if self.original_branch and self.original_branch not in branches:
            branches.insert(0, self.original_branch)
        if settings.DEBUG:
            branches.insert(0, "")  # unknown local branch
        return branches

    @property
    def original_commit_url(self) -> str:
        if not self.original_commit:
            return ""
        return f"{self.project.repository}/commit/{self.original_commit}"

    @property
    def markers(self) -> list[str]:
        metadata = self.last_result.metadata if self.last_result else {}
        # TODO: Consider making 'annotations' and/or 'tags' a proper field
        values = metadata.get("annotations", []) + metadata.get("tags", [])
        if self.disabled:
            values.append("disabled")
        return values

    @property
    def command(self) -> list[tuple[str, bool]]:
        return self.last_result.command if self.last_result else []

    @property
    def error_indicators(self) -> list[str]:
        if self.suite and self.suite.error_indicators:
            return self.suite.error_indicators
        return self.project.error_indicators

    @property
    def skipped_indicators(self) -> list[str]:
        if self.suite and self.suite.skipped_indicators:
            return self.suite.skipped_indicators
        return self.project.skipped_indicators

    @property
    def failure_rate_humanized(self) -> str:
        if self.failure_rate < 0:
            return "—"
        return f"{self.failure_rate:.1%}"

    @property
    def block_rate_humanized(self) -> str:
        if self.block_rate < 0:
            return "—"
        return f"{self.block_rate:.1%}"

    @property
    def average_duration_humanized(self) -> str:
        if self.average_duration < 0:
            return "—"
        return f"{self.average_duration:.1f}s"

    @property
    def failure_rate_delta(self) -> float:
        previous = timezone.now() - timedelta(days=1)
        if record := self.history.filter(timestamp__lte=previous).first():
            return self.failure_rate - record.failure_rate
        return 0

    @property
    def block_rate_delta(self) -> float:
        previous = timezone.now() - timedelta(days=1)
        if record := self.history.filter(timestamp__lte=previous).first():
            return self.block_rate - record.block_rate
        return 0

    def update_failure_rate(self) -> bool:
        old = self.failure_rate
        results = self.results.filter(
            branch__in=self.significant_branches,
        ).order_by("-created_at")
        if not results.exists():
            return False

        results = results[: self.project.sample_count]
        failed = sum(result.status in Status.test_failed() for result in results)
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

        results = results[: self.project.sample_count]
        failed = sum(result.status in Status.merge_blocked() for result in results)
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
            status__in=Status.measurable(),
            duration__gt=0,
        ).order_by("-created_at")
        if not results.exists():
            return False

        results = results[: self.project.sample_count]
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
        updated = any(
            [
                self.update_failure_rate(),
                self.update_block_rate(),
                self.update_average_duration(),
            ]
        )
        if updated:
            self.history.create_from_test(self)
        return updated

    def save(self, *args, **kwargs):
        if self.pk:
            self._update_last_result()
        if self.disabled_platforms:
            log.info(f"Disabling test based on platforms: {self}")
            self.disabled = True
        if self.failure_rate == 0:
            log.info(f"Restoring test based on failure rate: {self}")
            self.disabled = False
            self.disabled_platforms = []
        self.enabled = bool(
            not self.disabled
            and self.last_result
            and self.last_result.status not in Status.test_disabled()
        )
        super().save(*args, **kwargs)

    def _update_last_result(self):
        self.last_result = (
            self.results.filter(branch=self.project.default_branch)
            .order_by("-created_at")
            .first()
        )
        if self.last_result and self.last_result.status == Status.SKIPPED:
            if result := (
                self.results.filter(
                    branch=self.last_result.branch, commit=self.last_result.commit
                )
                .exclude(status=Status.SKIPPED)
                .order_by("-created_at")
                .first()
            ):
                self.last_result = result


class Result(models.Model):
    suite = models.ForeignKey(
        Suite, null=True, blank=True, on_delete=models.SET_NULL, related_name="results"
    )
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")

    branch = models.CharField(max_length=500, default="", db_index=True)
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
    def test_name(self) -> str:
        if self.suite and self.suite.name != DEFAULT_SUITE:
            return f"{self.suite.name} › {self.test.name}"
        return self.test.name

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
    def command(self) -> list[tuple[str, bool]]:
        """Returns a list of (line, copyable) tuples."""

        def copyable(line: str) -> bool:
            line = line.strip()
            return bool(line) and not line.startswith("#")

        if suite := self.suite or self.test.suite:
            if pattern := suite.local_command:
                try:
                    command = pattern.format(test=self.test)
                    lines = command.split("\n")
                    return [
                        (CHECKOUT_COMMAND.format(branch=self.branch), True),
                        ("\n", False),
                        ("# then", False),
                        ("\n", False),
                    ] + [(line, copyable(line)) for line in lines]

                except (KeyError, AttributeError) as e:
                    error = repr(e)
                    log.error(f"Invalid local command for {suite}: {error}")
                    return [(pattern, False), (f"# invalid pattern: {error}", False)]
        return []

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
    def originated_from_branch(self) -> bool:
        return (
            self.branch == self.test.original_branch
            and self.branch not in self.test.project.default_branches
        )

    @property
    def run_url(self) -> str:
        if run_id := self.metadata.get("GITHUB_RUN_ID"):
            url = f"{self.test.project.repository}/actions/runs/{run_id}"
            if number := self.metadata.get("CI_PR_NUMBER"):
                url += f"?pr={number}"
            return url
        return ""

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
            error_indicators=self.test.error_indicators,
            skipped_indicators=self.test.skipped_indicators,
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
