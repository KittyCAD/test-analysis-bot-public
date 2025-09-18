from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse
from django.utils import timezone

import log

from tab.core.models import Organization
from tab.projects.models import Project, Result, Suite, Test

from .constants import ALERT_CACHE_KEY, ALERT_CACHE_TIMEOUT, DELTA_THRESHOLD
from .helpers import send_slack_message
from .managers import HistoryManager
from .types import Message


class History(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="history")
    result = models.ForeignKey(
        Result, null=True, blank=True, on_delete=models.SET_NULL, related_name="history"
    )

    failure_rate = models.FloatField()
    block_rate = models.FloatField()
    average_duration = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    objects: HistoryManager = HistoryManager()

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["test", "timestamp"]),
        ]
        verbose_name_plural = "Histories"

    def __str__(self):
        return f"{self.test.project.name} @ {self.timestamp.date()}"

    @property
    def label(self) -> str:
        return self.test.project.name + " › " + self.test.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.create_alert()

    def create_alert(self) -> bool:
        if not self.test.enabled:
            return False

        if self.test.failure_rate_delta < DELTA_THRESHOLD:
            return False

        key = f"{ALERT_CACHE_KEY}:{self.test.id}"
        if cache.get(key):
            log.debug(f"Skipped redundant alert for test: {self.test}")
            return False

        alert = Alert.objects.create(history=self)
        log.warning(str(alert))
        if not alert.send():
            log.warning(f"Unable to send alert for test: {self.test}")
            return False

        cache.set(key, True, timeout=ALERT_CACHE_TIMEOUT)
        return True


class Team(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    slack_channel_name = models.CharField(max_length=100)

    alerted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["organization", "slack_channel_name"]
        unique_together = ["organization", "slack_channel_name"]

    def __str__(self):
        return f"{self.organization} › {self.slack_channel_name}"

    @property
    def recently_alerted(self):
        threshold = timezone.now() - timedelta(hours=1)
        return self.alerted_at and self.alerted_at > threshold

    def save(self, *args, **kwargs):
        if label := self.slack_channel_name.strip("# "):
            self.slack_channel_name = "#" + label
        super().save(*args, **kwargs)


class Subscription(models.Model):
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="subscriptions"
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="subscriptions"
    )
    suite = models.ForeignKey(
        Suite,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    test = models.CharField(max_length=500, null=True, blank=True)

    primary = models.BooleanField(default=True)

    class Meta:
        unique_together = ["team", "project", "suite", "test"]

    def __str__(self):
        return f"{self.team} › {self.project}"


class Alert(models.Model):
    history = models.OneToOneField(
        History, on_delete=models.CASCADE, related_name="alert"
    )

    url = models.URLField(null=True, blank=True, verbose_name="URL")

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.message)

    @property
    def message(self):
        return self.build()

    @property
    def teams(self) -> list[Team]:
        # TODO: Match by specificity first
        # TODO: Implement test name substring matching
        # TODO: Cross-post message URL to secondary teams
        subscriptions = Subscription.objects.filter(
            primary=True, project=self.history.test.project
        )
        return [subscription.team for subscription in subscriptions]

    def build(self, *, test: bool = False) -> Message:
        text = f"Failure rate increased by {self.history.test.failure_rate_delta:.1%} today"
        url = settings.BASE_URL + reverse(
            "projects:test-results",
            args=[self.history.test.project.path, self.history.test.id],
        )
        extra = self.history.result.message if self.history.result else None
        return Message(text, self.history.label, url, extra=extra or "", test=test)

    def send(self, *, test: bool = False, force: bool = False) -> int:
        count = 0
        message = self.build(test=test)
        for team in self.teams:
            if team.recently_alerted and not force:
                log.info(f"Skipped redundant alert for team: {team}")
                continue
            if url := send_slack_message(
                team.organization, team.slack_channel_name, message
            ):
                team.alerted_at = timezone.now()
                team.save()
                self.url = self.url or url
                self.sent_at = team.alerted_at
                self.save()
                count += 1
        return count
