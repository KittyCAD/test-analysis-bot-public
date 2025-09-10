from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse

import log

from tab.core.models import Organization
from tab.projects.models import Test

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

    objects = HistoryManager()

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
        self.alert()

    def alert(self) -> bool:
        if not self.test.enabled:
            return False

        if self.test.failure_rate_delta < DELTA_THRESHOLD:
            return False

        key = f"{ALERT_CACHE_KEY}:{self.test.id}"
        if cache.get(key):
            log.debug(f"Skipped redundant alert: {self.test}")
            return False

        # TODO: Match alert to subscribed teams
        alert = Alert.objects.create(history=self)
        alert.teams.set(Team.objects.filter(slack_channel_name__contains="test"))
        alert.save()

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

    def __str__(self):
        return f"{self.organization} › {self.slack_channel_name}"

    def save(self, *args, **kwargs):
        if label := self.slack_channel_name.strip("# "):
            self.slack_channel_name = "#" + label
        super().save(*args, **kwargs)


class Alert(models.Model):
    history = models.ForeignKey(
        History, on_delete=models.CASCADE, related_name="alerts"
    )
    teams = models.ManyToManyField(Team, related_name="alerts")

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

    def send(self, *, test: bool = False) -> int:
        count = 0
        message = self.message
        message.text = f"[TEST] {message.text}" if test else message.text
        for team in self.teams.all():
            if send_slack_message(team.organization, team.slack_channel_name, message):
                count += 1
        return count
