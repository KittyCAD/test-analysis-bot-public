from django.contrib.humanize.templatetags.humanize import naturaltime
from django.utils.html import format_html

import django_tables2 as tables

from .models import Test


class TestTable(tables.Table):
    name = tables.Column(verbose_name="Test Name")
    failure_rate = tables.Column(verbose_name="Failure Rate")
    average_duration = tables.Column(verbose_name="Average Duration")
    updated_at = tables.DateTimeColumn(verbose_name="Last Run")

    class Meta:
        model = Test
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "name",
            "failure_rate",
            "average_duration",
            "updated_at",
        )
        attrs = {"class": "table table-hover"}
        per_page = 15
        order_by = "-failure_rate"

    def render_failure_rate(self, value):
        if value < 0:
            return "—"
        return f"{value*100:.1f}%"

    def render_average_duration(self, value):
        if value < 0:
            return "—"
        return f"{value:.1f}s"

    def render_updated_at(self, value):
        return naturaltime(value)
