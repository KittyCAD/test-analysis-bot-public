from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import User

if TYPE_CHECKING:
    from .models import Project


def humanize_duration(value: float | None) -> str:
    """Format duration in seconds as XmXs when over a minute."""
    if value is None or value < 0:
        return "—"
    if value >= 100:  # 3 or more digits
        minutes = int(value // 60)
        seconds = int(value % 60)
        return f"{minutes}m{seconds}s"
    return f"{value:.1f}s"


def get_disabled_test_metrics(project: Project) -> dict[User, dict[str, int]]:
    """Compute statistics on disabled tests grouped by user."""

    # Get all tests that were ever disabled
    tests = project.tests.filter(disabled_user__isnull=False).select_related(
        "disabled_user"
    )

    # Group by user and current status
    data = {}
    for test in tests:
        user: User = test.disabled_user  # type: ignore[assignment]
        if user not in data:
            data[user] = {
                "total": 0,
                "disabled": 0,
                "enabled": 0,
            }

        data[user]["total"] += 1
        if test.disabled_at:
            data[user]["disabled"] += 1
        else:
            data[user]["enabled"] += 1

    return data
