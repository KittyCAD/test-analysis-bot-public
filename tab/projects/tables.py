from datetime import timedelta

from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe

import django_tables2 as tables
import log
from django_tables2 import A

from .models import Result, Run, Status, Suite, Test


def wrap(name: str) -> str:
    return mark_safe(name.replace("_", "_<wbr>"))


def color(
    text: str,
    value: float,
    lower_threshold: float,
    upper_threshold: float,
    icon: str = "",
    tooltip: str = "",
) -> str:
    if value > upper_threshold:
        brightness = 1.0
    elif value < lower_threshold:
        brightness = 0.0
    else:
        brightness = (value - lower_threshold) / (upper_threshold - lower_threshold)
    html = f'<span class="text-danger" style="filter: brightness({brightness});">{text}</span>'
    if icon and tooltip:
        html += f' <span title="{tooltip}"><i class="fa-solid fa-{icon}"></i></span>'
    return mark_safe(html)


class TestTable(tables.Table):
    name = tables.LinkColumn(
        "projects:test-results",
        args=[A("project__path"), A("id")],
        verbose_name="Test Name",
        attrs={"a": {"class": "text-body text-decoration-none fw-bold"}},
    )
    enabled = tables.BooleanColumn(
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
        },
    )
    failure_rate = tables.Column(
        verbose_name="Failure Rate",
        attrs={
            "td": {"class": "text-center"},
            "th": {
                "class": "text-center",
                "data-bs-toggle": "tooltip",
                "title": Test._meta.get_field("failure_rate").help_text,
            },
        },
    )
    block_rate = tables.Column(
        verbose_name="Block Rate",
        attrs={
            "td": {"class": "text-center"},
            "th": {
                "class": "text-center",
                "data-bs-toggle": "tooltip",
                "title": Test._meta.get_field("block_rate").help_text,
            },
        },
    )
    average_duration = tables.Column(
        verbose_name="Average Duration",
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
        },
    )
    updated_at = tables.DateTimeColumn(verbose_name="Last Reported")

    class Meta:
        model = Test
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "name",
            "enabled",
            "failure_rate",
            "block_rate",
            "average_duration",
            "updated_at",
        )
        per_page = 10
        order_by = "-failure_rate"

    def render_name(self, record: Test):
        return render_to_string(
            "projects/_markers.html",
            {"label": wrap(record.label), "markers": record.markers, "nowrap": True},
        )

    def render_enabled(self, value):
        icon = "check" if value else "xmark"
        color = "success" if value else "danger"
        return mark_safe(f'<i class="fa-solid fa-{icon} text-{color}"></i>')

    def render_failure_rate(self, record: Test):
        if suite := record.suite:
            return color(
                record.failure_rate_humanized,
                record.failure_rate,
                suite.failure_rate_lower_threshold,
                suite.failure_rate_upper_threshold,
            )
        return record.failure_rate_humanized

    def render_block_rate(self, record: Test):
        if suite := record.suite:
            return color(
                record.block_rate_humanized,
                record.block_rate,
                suite.block_rate_lower_threshold,
                suite.block_rate_upper_threshold,
            )
        return record.block_rate_humanized

    def render_average_duration(self, record: Test):
        if suite := record.suite:
            return color(
                record.average_duration_humanized,
                record.average_duration,
                suite.average_duration_lower_threshold,
                suite.average_duration_upper_threshold,
            )
        return record.average_duration_humanized

    def render_updated_at(self, value):
        age = timezone.now() - value
        opacity_class = "opacity-25" if age > timedelta(hours=12) else ""
        return mark_safe(
            f'<span class="text-nowrap {opacity_class}">{naturaltime(value)}</span>'
        )


class DisabledTestTable(tables.Table):
    select = tables.CheckBoxColumn(
        accessor="id",
        attrs={
            "th__input": {
                "class": "form-check-input border-dark",
                "onclick": "this.form.querySelectorAll('tbody input[type=checkbox]').forEach(cb => cb.checked = this.checked)",
            },
            "td__input": {"class": "form-check-input border-dark"},
        },
        orderable=False,
    )
    name = tables.LinkColumn(
        "projects:test-results",
        args=[A("project__path"), A("id")],
        verbose_name="Test Name",
        attrs={"a": {"class": "text-body text-decoration-none fw-bold"}},
    )
    failure_rate = tables.Column(
        verbose_name="Typically Fails",
        attrs={
            "td": {"class": "text-center"},
            "th": {
                "class": "text-center",
                "data-bs-toggle": "tooltip",
                "title": Test._meta.get_field("failure_rate").help_text,
            },
        },
    )
    disabled_reason = tables.Column(verbose_name="Reason Disabled")
    disabled_tracker = tables.Column(
        verbose_name="Tracker",
        attrs={
            "a": {"target": "_blank", "rel": "noopener noreferrer"},
        },
    )
    disabled_user = tables.Column(verbose_name="Last Updated")

    class Meta:
        model = Test
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "select",
            "name",
            "failure_rate",
            "disabled_reason",
            "disabled_tracker",
            "disabled_user",
        )
        order_by = "name"

    def render_name(self, record: Test):
        return render_to_string(
            "projects/_markers.html",
            {"label": wrap(str(record)), "markers": record.markers, "nowrap": True},
        )

    def render_failure_rate(self, record: Test):
        if suite := record.suite:
            return color(
                record.failure_rate_humanized,
                record.failure_rate,
                suite.failure_rate_lower_threshold,
                suite.failure_rate_upper_threshold,
            )
        return record.failure_rate_humanized

    def render_disabled_tracker(self, value: str, record: Test):
        if not value:
            return ""
        label = value.removeprefix(record.project.repository).strip("/")
        return mark_safe(
            f'<a href="{value}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )

    def render_disabled_user(self, value):
        if not value:
            return ""
        return value.email


class TestResultTable(tables.Table):
    status = tables.Column(verbose_name="Status")
    branch = tables.Column(
        attrs={
            "td": {"class": "text-center font-monospace"},
            "th": {"class": "text-center"},
        }
    )
    commit = tables.Column(
        attrs={
            "td": {"class": "text-center font-monospace"},
            "th": {"class": "text-center"},
        }
    )
    target = tables.Column(
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
        },
    )
    platform = tables.Column(
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
        },
    )
    duration = tables.Column(
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
        },
    )
    created_at = tables.DateTimeColumn(verbose_name="Reported")

    class Meta:
        model = Result
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "status",
            "branch",
            "commit",
            "target",
            "platform",
            "duration",
            "created_at",
        )
        per_page = 100
        order_by = "-created_at"

    def render_status(self, record: Result):
        status = Status(record.status)
        url = record.url
        if request := getattr(self, "request", None):
            if query_string := request.GET.urlencode():
                url += f"?{query_string}"
        html = f'<a href="{url}" class="badge text-bg-{status.color} fs-6 text-decoration-none">{status.label}</a>'
        if record.message:
            details = render_to_string(
                "projects/_result_modal.html", {"result": record}
            )
            html = f'<div class="d-flex align-items-center gap-1">{html} <span class="ms-1">{details}</span></div>'
        return mark_safe(html)

    def render_branch(self, record: Result):
        if not record.branch:
            return ""
        return mark_safe(
            f'<a href="{record.branch_url}" target="_blank">{record.branch}</a>'
        )

    def render_commit(self, record: Result):
        if not record.commit:
            return ""
        return mark_safe(
            f'<a href="{record.commit_url}" target="_blank">{record.commit_humanized}</a>'
        )

    def render_target(self, value, record: Result):
        if record.final:
            return value
        return mark_safe(f'<span class="opacity-25">{value}</span>')

    def render_platform(self, value, record: Result):
        if record.final:
            return value
        return mark_safe(f'<span class="opacity-25">{value}</span>')

    def render_duration(self, record: Result):
        html = f'<span class="d-inline-flex align-items-center gap-1">{record.duration_humanized}'
        if setup_duration := Run.objects.get_setup_duration(
            record.suite, record.branch, record.commit
        ):
            html += f'<span class="small">(+{setup_duration:.1f}s)</span>'
        html += "</span>"
        if not record.final:
            html = f'<span class="opacity-25">{html}</span>'
        return mark_safe(html)

    def render_created_at(self, value, record: Result):
        icon = "" if record.final else '<i class="fa-solid fa-repeat me-2"></i>'
        if url := record.run_url:
            link = f'<a href="{url}" target="_blank"><i class="fa-solid fa-external-link ms-2"></i></a>'
        else:
            link = ""
        html = f'<span class="text-nowrap">{icon}{naturaltime(value)}{link}</span>'
        if record.markers:
            html = render_to_string(
                "projects/_markers.html",
                {"label": mark_safe(html), "markers": record.markers, "nowrap": False},
            )
        if not record.final:
            html = f'<span class="opacity-25">{html}</span>'
        return mark_safe(html)


class ResultTable(TestResultTable):
    test = tables.Column(
        verbose_name="Test Name",
        accessor="test",
        order_by="test__name",
    )
    test__block_rate = tables.Column(
        verbose_name="Typically Blocks",
        attrs={
            "td": {"class": "text-center"},
            "th": {
                "class": "text-center",
                "data-bs-toggle": "tooltip",
                "title": Test._meta.get_field("block_rate").help_text,
            },
        },
    )
    branch = None
    commit = tables.Column(
        orderable=False,
        attrs={
            "td": {"class": "text-center font-monospace"},
            "th": {"class": "text-center"},
        },
    )

    class Meta:
        model = Result
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "test",
            "status",
            "test__block_rate",
            "commit",
            "duration",
            "target",
            "platform",
            "created_at",
        )
        per_page = 100
        order_by = "test", "target", "platform", "-created_at"

    def before_render(self, request):
        if request.GET.get("show") == "fails":
            log.debug(f"Overriding {self._meta.order_by=} to show disabled tests last")
            self.data.data = self.data.data.order_by("-status", *self._meta.order_by)
            page = request.GET.get("page")
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = 1
            self.paginate(page=page)

    def render_test(self, record: Result):
        url = record.test.url
        if record.branch != record.test.project.default_branch:
            url += f"?branch={record.branch}"
        label = wrap(record.test_label)
        return mark_safe(
            f'<a href="{url}" class="text-body text-decoration-none fw-bold">{label}</a>'
        )

    def render_test__block_rate(self, record: Result):
        if record.originated_from_branch and not record.new_failure:
            return "—"

        text = record.test.block_rate_humanized
        tooltip = icon = ""
        if record.new_failure and record.originated_from_branch:
            if record.test.block_rate <= 0:
                text = ""
            tooltip = "Current branch added this broken test"
            icon = "warning"
        elif record.new_failure:
            tooltip = "Current branch likely broke this test"
            icon = "warning"
        elif record.new_fix:
            tooltip = "Current branch may have fixed this test"
            icon = "star"

        return color(
            text,
            record.test.block_rate,
            (
                record.suite.block_rate_lower_threshold
                if record.suite
                else Suite._meta.get_field("block_rate_lower_threshold").default
            ),
            (
                record.suite.block_rate_upper_threshold
                if record.suite
                else Suite._meta.get_field("block_rate_upper_threshold").default
            ),
            icon,
            tooltip,
        )
