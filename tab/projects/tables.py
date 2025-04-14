from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.loader import render_to_string
from django.utils.html import format_html

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
    failure_rate = tables.Column(verbose_name="Failure Rate")
    average_duration = tables.Column(verbose_name="Average Duration")
    updated_at = tables.DateTimeColumn(verbose_name="Last Run")

    class Meta:
        model = Test
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "name",
            "enabled",
            "failure_rate",
            "average_duration",
            "updated_at",
        )
        per_page = 15
        order_by = "-failure_rate"

    def render_failure_rate(self, value, record):
        return record.failure_rate_humanized

    def render_average_duration(self, value, record):
        return record.average_duration_humanized

    def render_updated_at(self, value):
        return naturaltime(value)


class ResultTable(tables.Table):
    status = tables.Column(verbose_name="Status")
    branch = tables.Column(attrs={"td": {"class": "font-monospace"}})
    commit = tables.Column(attrs={"td": {"class": "font-monospace"}})
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
        )
        per_page = 20
        order_by = "-created_at"

    def render_commit(self, value):
        return value[:7]

    def render_duration(self, record: Result):
        return record.duration_humanized

    def render_created_at(self, value):
        return naturaltime(value)

    def render_status(self, record: Result):
        if not record.message:
            return format_html(
                '<span class="fw-bold">{}</span>', Status(record.status).label
            )
        return format_html(
            '<span class="fw-bold">{}</span> <span class="ms-2">{}</span>',
            Status(record.status).label,
            render_to_string("projects/_details.html", {"result": record}),
        )
