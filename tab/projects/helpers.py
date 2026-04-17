from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import User

import log
from github import GithubException
from requests.exceptions import RequestException

from tab.core.models import Organization

from .enums import Platform, Status, Target

if TYPE_CHECKING:
    from .models import Project, Result


def insert_breaks(text: str) -> str:
    """Insert line-break opportunities for long test names."""
    return text.replace("_", "_<wbr>").replace("::", "::<wbr>")


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


def rerun_failed_jobs(
    organization: Organization, project: Project, run_id: int
) -> str | None:
    assert "github.com" in project.repository, "Only GitHub is supported for now"
    github = organization.get_github_client()
    if not github:
        return None

    try:
        repo = github.get_repo(project.path)
        run = repo.get_workflow_run(run_id)
        status, _headers, body = run._requester.requestJson(
            "POST", f"{run.url}/rerun-failed-jobs"
        )
    except (GithubException, RequestException, OSError) as e:
        log.error(f"Unable to rerun failed jobs for {project.path} @ {run_id}: {e}")
        return None

    if status != 201:
        log.error(f"Unable to rerun failed jobs for {project.path} @ {run_id}: {body}")
        return None

    # GitHub Actions reuses the same run ID for subsequent attempts
    url = f"{project.repository}/actions/runs/{run_id}"
    log.info(f"Rerun failed jobs for {project.path} @ {run_id}: {url}")
    return url


def build_prompt(result: Result) -> str:
    from .models import Test

    lines: list[str] = []
    lines.append(
        "The following is exported from the Test Analysis Bot.\n"
        "Use it to help reproduce, debug, or fix the failure.\n"
        "Ask the user for approval before running any commands (for example tests, installs, or builds)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Test:** {result.test_label}")
    lines.append(f"- **Project:** {result.test.project.path}")
    lines.append(f"- **Status:** {Status(result.status).label}")
    lines.append(f"- **Duration:** {result.duration_humanized}")
    lines.append(f"- **Final retry:** {'yes' if result.final else 'no'}")
    if result.created_at:
        lines.append(f"- **Reported at:** {result.created_at.isoformat()}")
    lines.append(f"- **Branch:** {result.branch or '—'}")
    lines.append(f"- **Commit:** {result.commit or '—'}")
    lines.append(
        f"- **Target:** {Target(result.target).label if result.target else '—'}"
    )
    lines.append(
        f"- **Platform:** {Platform(result.platform).label if result.platform else '—'}"
    )
    markers = ", ".join(result.markers) if result.markers else "—"
    lines.append(f"- **Markers:** {markers}")
    fr_field = Test._meta.get_field("failure_rate")
    br_field = Test._meta.get_field("block_rate")
    lines.append(f"- **Failure rate:** {result.test.failure_rate_humanized}")
    lines.append(f"  _{fr_field.help_text}_")
    lines.append(f"- **Block rate:** {result.test.block_rate_humanized}")
    lines.append(f"  _{br_field.help_text}_")
    if result.pk and getattr(result.test, "pk", None):
        lines.append(f"- **Result page:** {result.url}")
    if result.status == Status.DISABLED:
        lines.append(
            "- **Ignored failure:** This run is recorded as an ignored failure because "
            "the test carried `fixme` or `disabled` markers, so the outcome is treated "
            "as intentionally non-blocking (pytest known-broken / quarantine pattern)."
        )
    if result.test.disabled_at:
        lines.append("")
        lines.append("## Manual disablement")
        lines.append("")
        lines.append(
            "This test is turned off in the Test Analysis Bot so it does not block "
            "merges while the disablement is active (separate from per-run markers)."
        )
        lines.append("")
        lines.append(f"- **Since:** {result.test.disabled_at.isoformat()}")
        if (user := result.test.disabled_user) is not None:
            who = user.email or user.get_username()
            lines.append(f"- **By:** {who}")
        if result.test.disabled_tracker:
            lines.append(f"- **Tracker:** {result.test.disabled_tracker}")
        if result.test.disabled_reason.strip():
            lines.append("")
            lines.append("```text")
            lines.append(result.test.disabled_reason.rstrip())
            lines.append("```")
    lines.append("")
    lines.append("## Links")
    lines.append("")
    link_lines = [
        ("Branch", result.branch_url),
        ("Commit", result.commit_url),
        ("Merge", result.merge_url),
        ("Run", result.run_url),
        ("Environment", result.environment_url),
    ]
    for label, url in link_lines:
        if url:
            lines.append(f"- **{label}:** {url}")
    if all(not url for _, url in link_lines):
        lines.append("_No links available._")
    lines.append("")
    if result.message:
        lines.append("## Message")
        lines.append("")
        lines.append("```text")
        lines.append(result.message.rstrip())
        lines.append("```")
        lines.append("")
    if result.command:
        lines.append("## Rerun locally")
        lines.append("")
        lines.append("```shell")
        lines.append("\n".join(line for line, _ in result.command).strip())
        lines.append("```")
        lines.append("")
    if result.logs:
        lines.append("## Additional logs")
        lines.append("")
        lines.append("```json")
        lines.append(result.logs_json)
        lines.append("```")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
