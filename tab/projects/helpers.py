from __future__ import annotations

import json
from datetime import timezone as dt_timezone
from typing import TYPE_CHECKING

from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

import log
from github import GithubException
from requests.exceptions import RequestException

from tab.core.models import Organization

from .enums import Platform, Status, Target

if TYPE_CHECKING:
    from .models import Project, Result, Test


METRICS_JSON_RESULTS_LIMIT = 10

METRICS_JSON_ROOT_META = "The following is exported from the Test Analysis Bot (TAB)."
METRICS_JSON_TEST_META = "These are the least-reliable and slowest tests in this project. Use this information to triage and suggest fixes."
METRICS_JSON_RESULT_META = "These are recent results for this test including at least one pass and one fail, if available."


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


def build_result_prompt(result: Result) -> str:
    test = result.test
    lines: list[str] = []
    lines.append("The following is exported from the Test Analysis Bot (TAB).")
    lines.append("")
    lines.append("Use this information to:")
    lines.append("")
    lines.append("1. Classify the failure")
    lines.append("2. Assess whether it is a real regression, flaky, or infra-related")
    lines.append("3. Explain which fields most strongly support that conclusion")
    lines.append("4. Suggest the most likely causes")
    lines.append("5. Propose a minimal fix if appropriate")
    lines.append("6. Verify the fix or ask the user to do so")
    lines.append("")
    lines.append("## Test identity")
    lines.append("")
    lines.append(f"- Repository: {test.project.path}")
    lines.append(f"- Name: {result.test_label}")
    lines.append(f"- Markers: {json.dumps(result.markers)}")
    lines.append(
        "- Date created: " + (test.created_at.isoformat() if test.created_at else "—")
    )
    lines.append(f"- Added in branch: {test.original_branch or '—'}")
    lines.append(f"- Added in commit: {test.original_commit or '—'}")
    lines.append("")
    lines.append("## Historical signals")
    lines.append("")
    lines.append(f"- Failure rate: {test.failure_rate_humanized}")
    lines.append(f"- Block rate: {test.block_rate_humanized}")
    lines.append(f"- Average duration: {test.average_duration_humanized}")
    lines.append("")
    for name in ("failure_rate", "block_rate", "average_duration"):
        field = test._meta.get_field(name)
        label = str(field.verbose_name).capitalize()  # type: ignore[union-attr]
        lines.append(f"_{label}: {field.help_text}_")  # type: ignore[union-attr]
    if test.disabled_at:
        lines.append("")
        lines.append("## Override behavior")
        lines.append("")
        lines.append(f"- Disabled: {str(bool(test.disabled_at)).lower()}")
        lines.append(f"- Disabled since: {test.disabled_at.isoformat()}")
        if test.disabled_reason.strip():
            lines.append(f"- Reason: {test.disabled_reason.strip()}")
        else:
            lines.append("- Reason: —")
        lines.append(f"- Tracker: {test.disabled_tracker or '—'}")
        updated_by = "—"
        if user := getattr(test, "disabled_user", None):
            updated_by = (
                user.email if getattr(user, "email", None) else user.get_username()
            )
        lines.append(f"- Last updated by: {updated_by}")
        lines.append("")
        lines.append(
            "_TAB has a feature to suppress failures in known broken or flaky tests._"
        )
        lines.append(
            "_This turns blocking failures into a non-blocking status to let PRs merge._"
        )
    lines.append("")
    lines.append("## Result details")
    lines.append("")
    lines.append(f"- Status: {Status(result.status).value}")
    lines.append(
        "- Reported at: "
        + (result.created_at.isoformat() if result.created_at else "—")
    )
    lines.append(f"- Duration: {result.duration_humanized}")
    lines.append(f"- Branch: {result.branch or '—'}")
    lines.append(f"- Commit: {result.commit or '—'}")
    lines.append(f"- Target: {Target(result.target).label if result.target else '—'}")
    lines.append(
        f"- Platform: {Platform(result.platform).label if result.platform else '—'}"
    )
    lines.append(f"- New failure: {str(result.new_failure).lower()}")
    lines.append("")
    lines.append(
        "_New failure: History data indicates the test is only blocking this branch._"
    )
    if result.message:
        lines.append("")
        lines.append("## Failure message")
        lines.append("")
        lines.append("```text")
        lines.append(result.message.rstrip())
        lines.append("```")
    lines.append("")
    lines.append("## Rerun locally")
    lines.append("")
    if result.command:
        lines.append("```shell")
        lines.append("\n".join(line for line, _ in result.command).strip())
        lines.append("```")
    else:
        lines.append("[TODO: add this]")
    lines.append("")
    lines.append("_Use this to reproduce the failure and validate fixes._")
    lines.append("_Do not discard uncommitted changes without user approval._")
    if result.logs:
        lines.append("")
        lines.append("## Additional logs")
        lines.append("")
        lines.append("```json")
        lines.append(result.logs_json)
        lines.append("```")
    return "\n".join(lines).strip() + "\n"


def _metrics_json_results_for_test(test: Test) -> list:
    """Select up to METRICS_JSON_RESULTS_LIMIT results for export.

    Includes the most recent passing run (``status == passed``), if any, and the
    most recent merge-blocked run (failure / error / timeout / unexpected pass),
    if any, then fills remaining slots with the newest runs (deduplicated).
    """
    # Local import: `models` imports this module at load time.
    from .models import Result

    pass_result = (
        test.results.filter(status=Status.PASSED).order_by("-created_at").first()
    )
    blocked_statuses = [s.value for s in Status.merge_blocked()]
    fail_result = (
        test.results.filter(status__in=blocked_statuses).order_by("-created_at").first()
    )

    chosen_ids: list[int] = []
    seen: set[int] = set()

    def add(r: Result | None) -> None:
        if r is not None and r.pk not in seen:
            seen.add(r.pk)
            chosen_ids.append(r.pk)

    add(pass_result)
    add(fail_result)

    if len(chosen_ids) < METRICS_JSON_RESULTS_LIMIT:
        for r in test.results.order_by("-created_at")[:100]:
            if len(chosen_ids) >= METRICS_JSON_RESULTS_LIMIT:
                break
            add(r)

    if not chosen_ids:
        return []

    rows = list(test.results.filter(pk__in=chosen_ids))
    by_pk = {r.pk: r for r in rows}
    ordered = [by_pk[pk] for pk in chosen_ids if pk in by_pk]
    ordered.sort(key=lambda r: r.created_at, reverse=True)
    return ordered[:METRICS_JSON_RESULTS_LIMIT]


def build_metrics_json(project: Project, tests: list[Test]) -> str:
    # Local import: `models` imports this module at load time.
    from .models import Result

    def result_row(r: Result) -> dict:
        created = r.created_at
        if created and django_timezone.is_aware(created):
            created = created.astimezone(dt_timezone.utc)
        created_str = created.strftime("%Y-%m-%dT%H:%M:%SZ") if created else None

        return {
            "_meta": METRICS_JSON_RESULT_META,
            "id": r.pk,
            "status": r.status,
            "branch": r.branch or None,
            "commit": r.commit or None,
            "target": r.target or None,
            "platform": r.platform or None,
            "final": r.final,
            "duration": r.duration,
            "created_at": created_str,
            "message": r.message or None,
            "url": r.url,
            "suite_id": r.suite_id,
            "metadata": r.metadata or {},
        }

    now = django_timezone.now()
    if django_timezone.is_aware(now):
        now = now.astimezone(dt_timezone.utc)
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    test_rows = []
    for test in tests:
        lr = test.last_result
        selected = _metrics_json_results_for_test(test)
        result_rows = [result_row(r) for r in selected]
        test_rows.append(
            {
                "_meta": METRICS_JSON_TEST_META,
                "test_id": test.pk,
                "test_label": str(test),
                "suite": test.suite.name if test.suite else None,
                "failure_rate": None if test.failure_rate < 0 else test.failure_rate,
                "block_rate": None if test.block_rate < 0 else test.block_rate,
                "average_duration_seconds": (
                    None if test.average_duration < 0 else test.average_duration
                ),
                "last_result_status": lr.status if lr else None,
                "last_result_branch": lr.branch if lr else None,
                "test_results_url": test.url,
                "results": result_rows,
            }
        )

    payload = {
        "_meta": METRICS_JSON_ROOT_META,
        "repository": project.path,
        "repository_url": project.repository,
        "generated_at": generated_at,
        "tests": test_rows,
    }

    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
