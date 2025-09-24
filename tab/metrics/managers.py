from datetime import timedelta
from typing import TYPE_CHECKING, cast

from django.db import models
from django.utils import timezone

import log

from tab.projects.models import Result, Test

if TYPE_CHECKING:
    from .models import History


class HistoryManager(models.Manager):
    def create_from_test(self, test: Test, result: Result | None = None):
        limit = timezone.now() - timedelta(hours=1)
        if self.filter(test=test, timestamp__gte=limit).exists():
            log.debug(f"Skipped redundant metric creation: {test}")
            return None

        history = self.create(
            test=test,
            result=result,
            failure_rate=test.failure_rate,
            block_rate=test.block_rate,
            average_duration=test.average_duration,
        )

        cutoff = timezone.now() - timedelta(weeks=26)
        if count := self.filter(test=test, timestamp__lt=cutoff).delete()[0]:
            log.debug(f"Deleted {count} old metrics")

        return history

    def get_data(self, test: Test, weeks: float) -> list[dict]:
        data = []
        cutoff = timezone.now() - timedelta(weeks=weeks)
        histories = self.filter(timestamp__gte=cutoff).order_by("timestamp")
        for history in cast(list["History"], histories):
            data.append(
                {
                    "date": history.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "failure_rate": round(history.failure_rate * 100, 1),
                    "block_rate": round(history.block_rate * 100, 1),
                    "average_duration": round(history.average_duration, 1),
                }
            )
        if not data:
            data.append(
                {
                    "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
                    "failure_rate": round(test.failure_rate * 100, 1),
                    "block_rate": round(test.block_rate * 100, 1),
                    "average_duration": round(test.average_duration, 1),
                }
            )
        if len(data) < 10:
            data.insert(
                0,
                {
                    "date": cutoff.strftime("%Y-%m-%d %H:%M"),
                    "failure_rate": data[0]["failure_rate"],
                    "block_rate": data[0]["block_rate"],
                    "average_duration": data[0]["average_duration"],
                },
            )
        return data
