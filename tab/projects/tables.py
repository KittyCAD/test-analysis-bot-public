from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

import django_tables2 as tables
from django_tables2 import A

from .models import Result, Status, Test


class TestTable(tables.Table):
    name = tables.LinkColumn(
        "projects:test-detail",
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
    updated_at = tables.DateTimeColumn(verbose_name="Last Run")

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
        name = record.name
        if record.markers:
            markers = render_to_string(
                "projects/_markers.html", {"markers": record.markers}
            )
            return mark_safe(f"{name} {markers}")
        return name

    def render_enabled(self, value):
        icon = "check" if value else "xmark"
        color = "success" if value else "danger"
        return mark_safe(f'<i class="fa-solid fa-{icon} text-{color}"></i>')

    def render_failure_rate(self, record: Test):
        return record.failure_rate_humanized

    def render_block_rate(self, record: Test):
        return record.block_rate_humanized

    def render_average_duration(self, record):
        return record.average_duration_humanized

    def render_updated_at(self, value, record: Test):
        when = naturaltime(value)
        if not record.last_result:
            return when
        status = Status(record.last_result.status)
        return mark_safe(
            f'{when} <span class="badge text-bg-{status.color} ms-1">{status.label}</span>'
        )


class ResultTable(tables.Table):
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
        per_page = 100
        order_by = "-created_at"

    def render_status(self, record: Result):
        status = Status(record.status)
        html = f'<span class="badge text-bg-{status.color} fs-6">{status.label}</span>'
        if record.message:
            details = render_to_string("projects/_details.html", {"result": record})
            html = f'<div class="d-flex align-items-center gap-1">{html} <span class="ms-1">{details}</span></div>'
        return mark_safe(html)

    def render_branch(self, record):
        if not record.branch:
            return ""
        return mark_safe(
            f'<a href="{record.branch_url}" target="_blank">{record.branch}</a>'
        )

    def render_commit(self, record):
        if not record.commit:
            return ""
        return mark_safe(
            f'<a href="{record.commit_url}" target="_blank">{record.commit_humanized}</a>'
        )

    def render_duration(self, record: Result):
        return record.duration_humanized

    def render_created_at(self, value, record: Result):
        html = "" if record.final else '<i class="fa-solid fa-repeat me-2"></i>'
        html += naturaltime(value)
        if record.markers:
            markers = render_to_string(
                "projects/_markers.html", {"markers": record.markers}
            )
            html += f" {markers}"
        return mark_safe(html)
