from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe

import django_tables2 as tables
from django_tables2 import A

from .constants import SAMPLE_COUNT
from .models import Result, Status, Test


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
                "title": lambda table: table._meta.model().failure_rate_help,
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
                "title": lambda table: table._meta.model().block_rate_help,
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
    updated_at = tables.DateTimeColumn(verbose_name="Last Updated")

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
        if record.markers:
            return render_to_string(
                "projects/_markers.html",
                {"label": record.name, "markers": record.markers},
            )
        return record.name

    def render_enabled(self, value):
        icon = "check" if value else "xmark"
        color = "success" if value else "danger"
        return mark_safe(f'<i class="fa-solid fa-{icon} text-{color}"></i>')

    def render_failure_rate(self, record: Test):
        return record.failure_rate_humanized

    def render_block_rate(self, record: Test):
        return record.block_rate_humanized

    def render_average_duration(self, record: Test):
        return record.average_duration_humanized

    def render_updated_at(self, value):
        return mark_safe(f'<span class="text-nowrap">{naturaltime(value)}</span>')


class DisabledTestTable(tables.Table):
    select = tables.CheckBoxColumn(
        accessor="id",
        attrs={
            "th__input": {
                "class": "form-check-input",
                "onclick": "this.form.querySelectorAll('tbody input[type=checkbox]').forEach(cb => cb.checked = this.checked)",
            },
            "td__input": {"class": "form-check-input"},
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
                "title": lambda table: table._meta.model().failure_rate_help,
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
        if record.markers:
            return render_to_string(
                "projects/_markers.html",
                {"label": record.name, "markers": record.markers},
            )
        return record.name

    def render_failure_rate(self, record: Test):
        return record.failure_rate_humanized

    def render_disabled_tracker(self, value):
        if not value:
            return ""
        return mark_safe(
            f'<a href="{value}" target="_blank" rel="noopener noreferrer">{value}</a>'
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
    created_at = tables.DateTimeColumn(verbose_name="When")

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
        per_page = SAMPLE_COUNT
        order_by = "-created_at"

    def render_status(self, record: Result):
        status = Status(record.status)
        html = f'<span class="badge text-bg-{status.color} fs-6">{status.label}</span>'
        if record.message:
            details = render_to_string("projects/_details.html", {"result": record})
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
        if not record.final:
            return mark_safe(f'<span class="opacity-25">{value}</span>')
        return value

    def render_platform(self, value, record: Result):
        if not record.final:
            return mark_safe(f'<span class="opacity-25">{value}</span>')
        return value

    def render_duration(self, record: Result):
        html = record.duration_humanized
        if not record.final:
            html = f'<span class="opacity-25">{html}</span>'
        return mark_safe(html)

    def render_created_at(self, value, record: Result):
        icon = "" if record.final else '<i class="fa-solid fa-repeat me-2"></i>'
        html = f'<span class="text-nowrap">{icon}{naturaltime(value)}</span>'
        if record.markers:
            html = render_to_string(
                "projects/_markers.html",
                {"label": mark_safe(html), "markers": record.markers},
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
    test__failure_rate = tables.Column(
        verbose_name="Typically Fails",
        attrs={
            "td": {"class": "text-center"},
            "th": {"class": "text-center"},
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
            "test__failure_rate",
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
            self.data.data = self.data.data.order_by(
                "-status", "test", "target", "platform", "-created_at"
            )
        self.paginate()

    def render_test(self, record: Result):
        url = reverse(
            "projects:test-results", args=[record.test.project.path, record.test.id]
        )
        return mark_safe(
            f'<a href="{url}?branch={record.branch}" class="text-body text-decoration-none fw-bold">{record.test.name}</a>'
        )

    def render_test__failure_rate(self, record: Result):
        return record.test.failure_rate_humanized
