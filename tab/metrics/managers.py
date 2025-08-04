from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

import log

from tab.projects.models import Test

if TYPE_CHECKING:
    from .models import History


class HistoryManager(models.Manager):
    def create_from_test(self, test: Test):
        limit = timezone.now() - timedelta(hours=1)
        if self.filter(test=test, timestamp__gte=limit).exists():
            log.debug(f"Skipping redundant metric creation")
            return

        history = self.create(
            test=test,
            failure_rate=test.failure_rate,
            block_rate=test.block_rate,
            average_duration=test.average_duration,
        )

        cutoff = timezone.now() - timedelta(weeks=3)
        if count := self.filter(test=test, timestamp__lt=cutoff).delete()[0]:
            log.debug(f"Deleted {count} old metrics")

        return history

    def get_data(self, days: int = 7) -> list[dict]:
        chart_data = []
        cutoff_date = timezone.now() - timedelta(days=days)
        histories = self.filter(timestamp__gte=cutoff_date).order_by("timestamp")
        history: "History"
        for history in histories:  # type: ignore[assignment]
            chart_data.append(
                {
                    "date": history.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "failure_rate": round(history.failure_rate * 100, 1),
                    "block_rate": round(history.block_rate * 100, 1),
                    "average_duration": round(history.average_duration, 1),
                }
            )
        return chart_data
