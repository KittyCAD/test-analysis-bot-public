from datetime import timedelta
from typing import TYPE_CHECKING, cast

from django.db import models
from django.utils import timezone

import log

from tab.projects.models import Result, Run, Suite, Test

from .constants import HISTORY_CHART_TARGET_POINTS

if TYPE_CHECKING:
    from .models import SuiteHistory, TestHistory


def format_percentage(value: float, decimals: int = 1) -> str:
    if value < 0:
        return "?"
    return f"{round(value * 100, decimals)}%"


def format_duration(value: float, decimals: int = 1) -> str:
    if value < 0:
        return "?"
    return f"{round(value, decimals)}s"


def chart_bucket_hours(weeks: float) -> float:
    """Hours per bucket so a weeks window yields ~HISTORY_CHART_TARGET_POINTS."""
    return max(1.0, (weeks * 7 * 24) / HISTORY_CHART_TARGET_POINTS)


def downsample_histories(histories: list, bucket_hours: float) -> list:
    """Keep the last sample in each time bucket (histories must be ascending)."""
    if bucket_hours <= 0:
        return histories
    bucket_seconds = bucket_hours * 3600
    buckets = {}
    for history in histories:
        key = int(history.timestamp.timestamp() // bucket_seconds)
        buckets[key] = history
    return [buckets[key] for key in sorted(buckets)]


class TestHistoryManager(models.Manager):
    def create_from_test(self, test: Test, result: Result | None = None):
        limit = timezone.now() - timedelta(hours=1)
        if self.filter(test=test, timestamp__gte=limit).exists():
            log.debug(f"Skipped redundant metric creation: {test}")
            return None
        if test.average_duration < 0:
            log.debug(f"Skipped metric creation for new test")
            return None

        history: TestHistory = self.create(  # type: ignore[assignment]
            test=test,
            result=result,
            failure_rate=test.failure_rate,
            block_rate=test.block_rate,
            average_duration=test.average_duration,
        )
        history.evaluate()

        cutoff = timezone.now() - timedelta(weeks=26)
        if count := self.filter(test=test, timestamp__lt=cutoff).delete()[0]:
            log.debug(f"Deleted {count} old metrics")

        return history

    def get_data(
        self, test: Test, weeks: float, *, bucket_hours: float | None = None
    ) -> list[dict]:
        cutoff = timezone.now() - timedelta(weeks=weeks)
        histories = list(self.filter(timestamp__gte=cutoff).order_by("timestamp"))
        if bucket_hours is None:
            bucket_hours = chart_bucket_hours(weeks)
        histories = downsample_histories(histories, bucket_hours)
        data = [
            {
                "date": history.timestamp.strftime("%Y-%m-%d %H:%M"),
                "failure_rate": format_percentage(history.failure_rate),
                "block_rate": format_percentage(history.block_rate),
                "average_duration": format_duration(history.average_duration),
            }
            for history in cast(list["TestHistory"], histories)
        ]
        if not data:
            data.append(
                {
                    "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
                    "failure_rate": format_percentage(test.failure_rate),
                    "block_rate": format_percentage(test.block_rate),
                    "average_duration": format_duration(test.average_duration),
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


class SuiteHistoryManager(models.Manager):
    def create_from_suite(self, suite: Suite, run: Run | None = None):
        if (
            suite.average_setup_duration < 0
            and suite.average_tests_duration < 0
            and suite.average_teardown_duration < 0
        ):
            log.debug(f"Skipped suite metric creation for new suite")
            return None

        values = {
            "run": run,
            "average_setup_duration": suite.average_setup_duration,
            "average_tests_duration": suite.average_tests_duration,
            "average_teardown_duration": suite.average_teardown_duration,
        }
        limit = timezone.now() - timedelta(hours=1)
        recent = self.filter(suite=suite, timestamp__gte=limit).first()
        if recent:
            for field, value in values.items():
                setattr(recent, field, value)
            recent.save(update_fields=list(values))
            return recent

        history: SuiteHistory = self.create(  # type: ignore[assignment]
            suite=suite,
            **values,
        )

        cutoff = timezone.now() - timedelta(weeks=26)
        if count := self.filter(suite=suite, timestamp__lt=cutoff).delete()[0]:
            log.debug(f"Deleted {count} old suite metrics")

        return history

    def get_data(
        self, suite: Suite, weeks: float, *, bucket_hours: float | None = None
    ) -> list[dict]:
        cutoff = timezone.now() - timedelta(weeks=weeks)
        histories = list(
            self.filter(timestamp__gte=cutoff, average_tests_duration__gte=0).order_by(
                "timestamp"
            )
        )
        if bucket_hours is None:
            bucket_hours = chart_bucket_hours(weeks)
        histories = downsample_histories(histories, bucket_hours)
        data = [
            self._point(history.timestamp, history)
            for history in cast(list["SuiteHistory"], histories)
        ]
        if not data and suite.average_tests_duration >= 0:
            data.append(self._point(timezone.now(), suite))
        return data

    @staticmethod
    def _point(timestamp, source: "SuiteHistory" | Suite) -> dict:
        return {
            "date": timestamp.isoformat(),
            "setup_duration": (
                None
                if source.average_setup_duration < 0
                else source.average_setup_duration
            ),
            "tests_duration": (
                None
                if source.average_tests_duration < 0
                else source.average_tests_duration
            ),
            "teardown_duration": (
                None
                if source.average_teardown_duration < 0
                else source.average_teardown_duration
            ),
        }
