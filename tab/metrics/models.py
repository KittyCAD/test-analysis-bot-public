from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse

import log

from tab.core.models import Organization
from tab.projects.models import Project, Suite, Test

from .constants import ALERT_CACHE_KEY, ALERT_CACHE_TIMEOUT, DELTA_THRESHOLD
from .helpers import send_slack_message
from .managers import HistoryManager
from .types import Message


class History(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="history")

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
            log.debug(f"Skipped redundant alert: {self.test}")
            return False

        alert = Alert.objects.create(history=self)
        log.warning(alert.message)
        alert.send()
        cache.set(key, True, timeout=ALERT_CACHE_TIMEOUT)
        return True


class Team(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    slack_channel_name = models.CharField(max_length=100)

    class Meta:
        ordering = ["organization", "slack_channel_name"]
        unique_together = ["organization", "slack_channel_name"]

    def __str__(self):
        return f"{self.organization} › {self.slack_channel_name}"

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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.message)

    @property
    def message(self):
        return Message(
            text=f"Test failure rate increased by {self.history.test.failure_rate_delta:.1%} today",
            label=self.history.test.project.name + " › " + self.history.test.name,
            url=settings.BASE_URL
            + reverse(
                "projects:test-results",
                args=[self.history.test.project.path, self.history.test.id],
            ),
        )

    @property
    def teams(self) -> list[Team]:
        # TODO: Match by specificity first
        # TODO: Report message URL to secondary teams
        subscriptions = Subscription.objects.filter(
            primary=True, project=self.history.test.project
        )
        return [subscription.team for subscription in subscriptions]

    def send(self, *, test: bool = False) -> int:
        count = 0
        message = self.message
        message.text = f"[TEST] {message.text}" if test else message.text
        for team in self.teams:
            if url := send_slack_message(
                team.organization, team.slack_channel_name, message
            ):
                count += 1
                if not self.url:
                    self.url = url
                    self.save()
        return count
