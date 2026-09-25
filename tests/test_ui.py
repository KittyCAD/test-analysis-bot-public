import re
from datetime import timedelta
from pathlib import Path

from django.urls import reverse
from django.utils import timezone

import pytest
from playwright.sync_api import Page

from tab.core.models import Organization
from tab.metrics.models import SuiteHistory, TestHistory
from tab.projects.enums import Status
from tab.projects.models import Project, Suite, Test
from tab.releases.enums import Type
from tab.releases.models import Environment, Release

from .utils import force_login, take_snapshot, wait_for_chart


@pytest.fixture(autouse=True)
def organization():
    organization = Organization.objects.create(
        name="Test Org",
        email_domain="example.com",
        repository_index="https://github.com/foo",
    )

    project = Project.objects.create(repository="https://github.com/foo/bar")
    # Long unbroken URL wider than card text-max-width — the link icon must
    # stay glued (no \\s before it) or Cytoscape wraps the glyph alone.
    staging = Environment.objects.create(
        project=project,
        name=Type.STAGING,
        url="wss://api.dev.zoo.dev/ws/modeling/commands",
    )
    production = Environment.objects.create(
        project=project, name=Type.PRODUCTION, url="https://api.example.com"
    )
    review = Environment.objects.create(
        project=project,
        name=Type.REVIEW,
        url="https://app-pr-1.example.com",
    )
    staging.dependencies.add(production)

    now = timezone.now()
    # Several close releases plus one older outlier so the change-history
    # timeline inserts a break marker (gap > max(median×5, 7 days)).
    release_specs = [
        (staging, "main", "aaa1111", timedelta(days=0)),
        (production, "main", "bbb2222", timedelta(days=1)),
        (staging, "main", "ccc3333", timedelta(days=2)),
        (production, "main", "ddd4444", timedelta(days=3)),
        (staging, "main", "eee5555", timedelta(days=4)),
        (production, "main", "fff6666", timedelta(days=18)),
        # One review release for the include-review snapshots.
        (review, "feature", "rev7777", timedelta(hours=12)),
    ]
    releases = []
    for environment, branch, commit, age in release_specs:
        release = Release.objects.create(
            environment=environment, branch=branch, commit=commit
        )
        Release.objects.filter(pk=release.pk).update(created_at=now - age)
        releases.append(release)
    releases[0].dependencies.add(releases[1])
    # Review → production so include-review snapshots show a dependency line.
    releases[-1].dependencies.add(releases[1])
    return organization


@pytest.mark.django_db
def test_releases(page: Page, live_server, admin_user):
    force_login(page, live_server, admin_user)
    page.goto(f"{live_server.url}{reverse('releases:index')}")

    assert page.get_by_text("Environment Dependencies").is_visible()
    environment_graph = page.locator("#environment-graph-data").evaluate(
        "el => el.textContent"
    )
    assert "wss://api.dev.zoo.dev/ws/modeling/commands" in environment_graph

    assert page.get_by_text("Change History").is_visible()
    release_graph = page.locator("#release-graph-data").evaluate("el => el.textContent")
    assert "aaa1111" in release_graph

    env_graph = page.locator('.releases-graph[data-graph="environment-graph-data"]')
    page.wait_for_function(
        "() => !!document.querySelector"
        "('.releases-graph[data-graph=\\'environment-graph-data\\']')._cy"
    )
    # Link icons must stay on the same visual line as their label. Cytoscape
    # wraps on /[\s\u200b]/ (NBSP included), so the suffix uses U+2060.
    link_icon_layout = env_graph.evaluate("""el => {
            const LINK_ICON = "↗";
            const labels = [];
            const orphanIconLines = [];
            const whitespaceBeforeIcon = [];
            el._cy
                .nodes()
                .filter(
                    (node) =>
                        !node.data("isHeader") &&
                        !node.data("isSpacer") &&
                        !node.data("isTimelineDot")
                )
                .forEach((node) => {
                    const label = String(node.data("label") || "");
                    labels.push(label);
                    if (/\\s↗/.test(label) || /\\u200b↗/.test(label)) {
                        whitespaceBeforeIcon.push(label);
                    }
                    const cached =
                        (node._private &&
                            node._private.rscratch &&
                            node._private.rscratch.labelWrapCachedLines) ||
                        null;
                    const visualLines = Array.isArray(cached)
                        ? cached
                        : label.split("\\n");
                    visualLines.forEach((visual) => {
                        if (String(visual).trim() === LINK_ICON) {
                            orphanIconLines.push(label);
                        }
                    });
                });
            return {
                labelCount: labels.length,
                withIcon: labels.filter((label) => label.includes(LINK_ICON))
                    .length,
                gluedWithJoiner: labels.filter((label) =>
                    label.includes("\\u2060" + LINK_ICON)
                ).length,
                orphanIconLines,
                whitespaceBeforeIcon,
            };
        }""")
    assert link_icon_layout["labelCount"] > 0
    assert link_icon_layout["withIcon"] > 0
    assert link_icon_layout["gluedWithJoiner"] == link_icon_layout["withIcon"]
    assert link_icon_layout["whitespaceBeforeIcon"] == []
    assert link_icon_layout["orphanIconLines"] == []

    release_graph_el = page.locator('.releases-graph[data-graph="release-graph-data"]')
    page.wait_for_function(
        "() => !!document.querySelector"
        "('.releases-graph[data-graph=\\'release-graph-data\\']')._cy"
    )
    release_link_icons = release_graph_el.evaluate("""el => {
            const LINK_ICON = "↗";
            const orphanIconLines = [];
            el._cy
                .nodes()
                .filter(
                    (node) =>
                        !node.data("isHeader") &&
                        !node.data("isSpacer") &&
                        !node.data("isTimelineDot") &&
                        !node.data("isTimelineHour") &&
                        !node.data("isTimelineEndpoint") &&
                        !node.data("isTimelineBreak")
                )
                .forEach((node) => {
                    const label = String(node.data("label") || "");
                    const cached =
                        (node._private &&
                            node._private.rscratch &&
                            node._private.rscratch.labelWrapCachedLines) ||
                        null;
                    const visualLines = Array.isArray(cached)
                        ? cached
                        : label.split("\\n");
                    visualLines.forEach((visual) => {
                        if (String(visual).trim() === LINK_ICON) {
                            orphanIconLines.push(label);
                        }
                    });
                });
            return { orphanIconLines };
        }""")
    assert release_link_icons["orphanIconLines"] == []

    # Timeline axis reaches the bottom of the gray card, not just the last tick.
    axis_to_bottom = release_graph_el.evaluate("""el => {
            const cy = el._cy;
            const axisEnd = cy.getElementById("timeline-axis-end");
            if (!axisEnd.nonempty()) {
                return { ok: false, reason: "missing axis end" };
            }
            const zoom = cy.zoom();
            const pan = cy.pan();
            const bottomY = (el.clientHeight - pan.y) / zoom;
            const axisY = axisEnd.position("y");
            return {
                ok: Math.abs(bottomY - axisY) <= 1.5,
                bottomY,
                axisY,
                height: el.clientHeight,
            };
        }""")
    assert axis_to_bottom["ok"], axis_to_bottom

    timeline_breaks = release_graph_el.evaluate(
        """el => el._cy.nodes().filter(node => node.data("isTimelineBreak")).length"""
    )
    assert timeline_breaks > 0

    lines = page.locator("#show-dependency-lines")
    review = page.locator("#show-review-releases")
    assert lines.is_checked()
    assert not review.is_checked()
    take_snapshot(page, "releases/lines-on-review-off")

    lines.uncheck()
    assert re.search(r"[?&]lines=false", page.url)
    assert not review.is_checked()
    take_snapshot(page, "releases/lines-off-review-off")

    with page.expect_navigation():
        review.check()
    lines = page.locator("#show-dependency-lines")
    review = page.locator("#show-review-releases")
    assert not lines.is_checked()
    assert review.is_checked()
    assert re.search(r"[?&]lines=false", page.url)
    assert re.search(r"[?&]review=true", page.url)
    assert "rev7777" in page.locator("#release-graph-data").evaluate(
        "el => el.textContent"
    )
    take_snapshot(page, "releases/lines-off-review-on")

    lines.check()
    assert not re.search(r"[?&]lines=false", page.url)
    assert review.is_checked()
    page.wait_for_function(
        "() => !!document.querySelector"
        "('.releases-graph[data-graph=\\'release-graph-data\\']')._cy"
    )
    review_dependency = page.locator(
        '.releases-graph[data-graph="release-graph-data"]'
    ).evaluate(
        """el => {
            const data = el._graphData || {};
            const reviewNode = (data.nodes || []).find(node =>
                String(node.label || "").includes("rev7777")
            );
            const cyEdges = el._cy
                .edges()
                .filter(edge => !edge.data("isTimeline")).length;
            if (!reviewNode) {
                return { dataEdges: 0, cyEdges, reviewId: null };
            }
            const dataEdges = (data.edges || []).filter(
                edge => edge.source === reviewNode.id
            ).length;
            const cyReviewEdges = el._cy
                .edges()
                .filter(
                    edge =>
                        !edge.data("isTimeline") &&
                        edge.source().id() === reviewNode.id
                ).length;
            return {
                dataEdges,
                cyEdges,
                cyReviewEdges,
                reviewId: reviewNode.id,
            };
        }"""
    )
    assert review_dependency["dataEdges"] > 0, review_dependency
    assert review_dependency["cyReviewEdges"] > 0, review_dependency
    take_snapshot(page, "releases/lines-on-review-on")


@pytest.mark.django_db
def test_troubleshooting_panel(page: Page, live_server, admin_user):
    project = Project.objects.get(repository="https://github.com/foo/bar")
    test = Test.objects.create(project=project, name="flaky-test")
    test.results.create(
        branch="main",
        commit="abc123",
        status=Status.FAILED,
        duration=1.0,
    )
    now = timezone.now()
    rates = [0.05, 0.08, 0.12, 0.18, 0.35, 0.55, 0.72, 0.80, 0.78, 0.82]
    for index, rate in enumerate(rates):
        history = TestHistory.objects.create(
            test=test,
            failure_rate=rate,
            block_rate=rate * 0.6,
            average_duration=1.0 + index * 0.1,
        )
        history.timestamp = now - timedelta(days=len(rates) - 1 - index)
        history.save(update_fields=["timestamp"])

    force_login(page, live_server, admin_user)
    url = f"{live_server.url}{reverse('projects:test-results', args=[project.path, test.id])}"

    page.goto(f"{url}?expand=false")
    panel = page.locator("details.troubleshooting")
    summary = page.get_by_text("Troubleshooting", exact=True)
    assert summary.is_visible()
    assert not panel.evaluate("el => el.open")
    take_snapshot(page, "projects/troubleshooting-collapsed")

    summary.click()
    assert panel.evaluate("el => el.open")

    # Hover a data point so the snapshot captures the chart tooltip
    canvas = page.locator("#failureRateChart")
    wait_for_chart(page, "failureRateChart", index=5)
    box = canvas.bounding_box()
    center = canvas.evaluate(
        "el => Chart.getChart(el).getDatasetMeta(0).data[5].getCenterPoint()"
    )
    assert box
    page.mouse.move(box["x"] + center["x"], box["y"] + center["y"])
    page.wait_for_function(
        "() => Chart.getChart('failureRateChart').tooltip.opacity === 1"
    )

    take_snapshot(page, "projects/troubleshooting-expanded")


@pytest.mark.django_db
def test_suite_troubleshooting_panel(page: Page, live_server, admin_user):
    project = Project.objects.get(repository="https://github.com/foo/bar")
    suite = Suite.objects.create(
        project=project,
        name="e2e",
        local_command=(
            'npm install\n\n# then\n\nnpm run test:e2e -- --grep="{test.name}"'
        ),
    )
    now = timezone.now()
    setups = [12.0, 13.0, 14.0, 16.0, 18.0, 20.0, 19.0, 17.0, 15.0, 14.0]
    tests = [70.0, 85.0, 100.0, 115.0, 130.0, 145.0, 138.0, 120.0, 105.0, 90.0]
    # Suites without a teardown step are normal, so some records have no value
    teardowns = [4.0, 4.5, -1, -1, 7.0, 8.0, 7.5, 6.5, 5.5, 5.0]
    for index, (setup, tests_duration, teardown) in enumerate(
        zip(setups, tests, teardowns)
    ):
        history = SuiteHistory.objects.create(
            suite=suite,
            average_setup_duration=setup,
            average_tests_duration=tests_duration,
            average_teardown_duration=teardown,
        )
        history.timestamp = now - timedelta(days=len(setups) - 1 - index)
        history.save(update_fields=["timestamp"])

    force_login(page, live_server, admin_user)
    url = f"{live_server.url}{reverse('projects:suite-tests', args=[project.path, suite.id])}"

    page.goto(f"{url}?expand=false")
    panel = page.locator("details.suite-troubleshooting")
    summary = page.get_by_text("Troubleshooting", exact=True)
    assert summary.is_visible()
    assert not panel.evaluate("el => el.open")
    take_snapshot(page, "projects/suite-troubleshooting-collapsed")

    summary.click()
    assert panel.evaluate("el => el.open")
    assert page.get_by_text("Suite Duration History").is_visible()
    assert page.get_by_text("Rerun Locally").is_visible()
    assert page.get_by_text("npm run test:e2e").is_visible()
    assert page.get_by_text("--grep").count() == 0

    canvas = page.locator("#suiteDurationChart")
    wait_for_chart(page, "suiteDurationChart", dataset=2, index=5)

    # A missing teardown stacks as zero so the tests band still fills to setup
    gap = page.evaluate("""() => {
            const chart = Chart.getChart('suiteDurationChart');
            const point = chart.getDatasetMeta(2).data[3];
            return chart.scales.y.getValueForPixel(point.y);
        }""")
    assert gap == pytest.approx(setups[3] + tests[3], abs=1.0)

    # Hover a data point so the snapshot captures the stacked duration tooltip
    box = canvas.bounding_box()
    center = canvas.evaluate(
        "el => Chart.getChart(el).getDatasetMeta(2).data[5].getCenterPoint()"
    )
    assert box
    page.mouse.move(box["x"] + center["x"], box["y"] + center["y"])
    page.wait_for_function(
        "() => Chart.getChart('suiteDurationChart').tooltip.opacity === 1"
    )

    # The tooltip anchors to the hovered point rather than the middle of the stack
    caret = page.evaluate("() => Chart.getChart('suiteDurationChart').tooltip.caretY")
    assert abs(caret - center["y"]) < 5

    take_snapshot(page, "projects/suite-troubleshooting-expanded")


@pytest.mark.django_db
def test_export_button(page: Page, live_server, admin_user):
    project = Project.objects.get(repository="https://github.com/foo/bar")
    test = Test.objects.create(project=project, name="flaky-test")
    test.results.create(
        branch="main",
        commit="abc123",
        status=Status.PASSED,
        duration=1.0,
    )

    force_login(page, live_server, admin_user)
    page.goto(
        f"{live_server.url}"
        f"{reverse('projects:test-results', args=[project.path, test.id])}"
    )

    button = page.locator("#export-button")
    assert button.is_visible()
    assert not button.evaluate("el => el.classList.contains('disabled')")

    with page.expect_download() as download_info:
        button.click()

    download = download_info.value
    assert download.suggested_filename == f"tab-export-foo-bar-test-{test.pk}.json"
    path = download.path()
    assert path is not None
    body = Path(path).read_text()
    assert '"name": "flaky-test"' in body

    button.locator("xpath=following-sibling::button").click()
    page.get_by_role("link", name="Preview Content").click()
    assert page.url.endswith(
        reverse("projects:test-export-page", args=[project.path, test.id])
    )
    assert '"name": "flaky-test"' in page.locator("pre").inner_text()
