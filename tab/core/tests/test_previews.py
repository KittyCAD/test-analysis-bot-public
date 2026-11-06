from datetime import timedelta
from io import BytesIO

from django.utils import timezone

import pytest
from PIL import Image

from tab.core.previews import (
    RECENT_RESULT_COUNT,
    _pluralize,
    _recent_statuses_for_test,
    is_unhealthy,
    render_disabled_preview_png,
    render_logo_preview_png,
    render_metrics_preview_png,
    render_project_preview_png,
    render_result_preview_png,
    render_suite_preview_png,
    render_test_preview_png,
)
from tab.projects.enums import Status
from tab.projects.models import Project, Suite, Test


def _assert_square_png(png: bytes, expect):
    image = Image.open(BytesIO(png))
    expect(image.size) == (512, 512)
    expect(image.format) == "PNG"


def describe_preview_pngs(expect):
    @pytest.fixture
    def project():
        return Project.objects.create(repository="https://github.com/preview/repo")

    @pytest.fixture
    def suite(project):
        return Suite.objects.create(
            project=project,
            name="unit",
            failure_rate_lower_threshold=0.10,
        )

    @pytest.mark.django_db
    def it_marks_high_failure_rate_unhealthy(project, suite):
        test = Test.objects.create(
            project=project, suite=suite, name="bad", failure_rate=0.4
        )
        expect(is_unhealthy(test)).is_(True)

    @pytest.mark.django_db
    def it_marks_low_failure_rate_healthy(project, suite):
        test = Test.objects.create(
            project=project, suite=suite, name="good", failure_rate=0.05
        )
        expect(is_unhealthy(test)).is_(False)
        _assert_square_png(render_test_preview_png(test), expect)

    @pytest.mark.django_db
    def it_renders_test_preview_with_result_statuses(project, suite):
        test = Test.objects.create(
            project=project,
            suite=suite,
            name="charted",
            failure_rate=0.4,
            block_rate=0.1,
            average_duration=2.0,
        )
        now = timezone.now()
        for index, status in enumerate(
            [Status.PASSED, Status.FAILED, Status.ERROR, Status.PASSED]
        ):
            result = test.results.create(
                branch="main",
                commit=f"c{index}",
                status=status,
                duration=1.0,
            )
            test.results.filter(pk=result.pk).update(
                created_at=now - timedelta(hours=4 - index)
            )

        _assert_square_png(render_test_preview_png(test), expect)
        expect(RECENT_RESULT_COUNT) == 20

    @pytest.mark.django_db
    def it_filters_recent_statuses_to_significant_branches(project, suite):
        test = Test.objects.create(
            project=project, suite=suite, name="branched", original_branch="feature"
        )
        now = timezone.now()
        main = test.results.create(
            branch="main", commit="m1", status=Status.PASSED, duration=1.0
        )
        feature = test.results.create(
            branch="other", commit="o1", status=Status.FAILED, duration=1.0
        )
        test.results.filter(pk=feature.pk).update(created_at=now)
        test.results.filter(pk=main.pk).update(created_at=now - timedelta(minutes=1))

        expect(_recent_statuses_for_test(test)) == [Status.PASSED]

    @pytest.mark.django_db
    def it_renders_result_preview_with_status_label(project, suite):
        test = Test.objects.create(project=project, suite=suite, name="a-test")
        result = test.results.create(
            branch="main", commit="abc", status=Status.FAILED, duration=1.0
        )
        _assert_square_png(render_result_preview_png(result), expect)

    @pytest.mark.django_db
    def it_renders_metrics_and_disabled_counts(project, suite):
        test = Test.objects.create(
            project=project,
            suite=suite,
            name="flaky",
            failure_rate=0.5,
            block_rate=0.1,
            average_duration=100,
            disabled_at=timezone.now(),
        )
        result = test.results.create(
            branch="main", commit="abc", status=Status.FAILED, duration=1.0
        )
        Test.objects.filter(pk=test.pk).update(last_result=result, enabled=False)
        _assert_square_png(render_disabled_preview_png(project), expect)
        _assert_square_png(render_metrics_preview_png(project), expect)

    @pytest.mark.django_db
    def it_renders_suite_and_project_counts(project, suite):
        Test.objects.create(project=project, suite=suite, name="t")
        _assert_square_png(render_suite_preview_png(suite), expect)
        _assert_square_png(render_project_preview_png(project, is_org=False), expect)

    @pytest.mark.django_db
    def it_falls_back_to_logo_for_empty_org():
        org = Project.objects.create(repository="https://github.com/lonely-org")
        _assert_square_png(render_project_preview_png(org, is_org=True), expect)
        _assert_square_png(render_logo_preview_png(), expect)

    def it_pluralizes_count_labels():
        expect(_pluralize(0, "Suite")) == "Suites"
        expect(_pluralize(1, "Suite")) == "Suite"
        expect(_pluralize(2, "Suite")) == "Suites"
        expect(_pluralize(1, "Unreliable test")) == "Unreliable test"
        expect(_pluralize(3, "Unreliable test")) == "Unreliable tests"
