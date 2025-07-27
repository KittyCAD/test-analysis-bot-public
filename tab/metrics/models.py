from django.db import models

from tab.projects.models import Test

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
