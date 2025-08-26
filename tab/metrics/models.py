from django.core.cache import cache
from django.db import models

import log

from tab.projects.models import Test

from .constants import ALERT_CACHE_KEY, ALERT_CACHE_TIMEOUT, DELTA_THRESHOLD
from .managers import HistoryManager


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

        # TODO: Send alerts to subscribed channels
        log.warning(
            f"Test failure rate increased by {self.test.failure_rate_delta:.1%} today: {self.test}"
        )
        cache.set(key, True, timeout=ALERT_CACHE_TIMEOUT)
        return True
