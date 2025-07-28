from datetime import timedelta

from django.db import models
from django.utils import timezone

import log

from tab.projects.models import Test


class HistoryManager(models.Manager):
    def create_from_test(self, test: Test):
        limit = timezone.now() - timedelta(hours=0)
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
