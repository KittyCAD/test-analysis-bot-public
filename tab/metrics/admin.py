from urllib.parse import urlparse

from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import Alert, History, Subscription, Team


@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")

    list_display = (
        "id",
        "test__project",
        "test__name",
        "failure_rate",
        "block_rate",
        "average_duration",
        "timestamp",
    )
    search_fields = (
        "test__project__repository",
        "test__name",
    )

    readonly_fields = (
        "test",
        "timestamp",
        "failure_rate",
        "block_rate",
        "average_duration",
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "slack_channel_name",
        "alerted_at",
    )
    list_filter = ("alerted_at",)
    search_fields = (
        "organization__name",
        "slack_channel_name",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    search_fields = (
        "team__organization__name",
        "team__slack_channel_name",
        "project__repository",
        "suite__name",
        "test",
    )
    list_display = (
        "id",
        "team",
        "primary",
        "project",
        "suite",
        "test",
    )
    list_filter = (
        "primary",
        "project",
        "suite",
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "_message",
        "_url",
        "_teams",
        "created_at",
    )
    search_fields = (
        "history__test__project__repository",
        "history__test__name",
    )

    @admin.display(description="Message")
    def _message(self, alert: Alert):
        return mark_safe(alert.message.html)

    @admin.display(description="URL")
    def _url(self, alert: Alert):
        if not alert.url:
            return None
        domain = urlparse(alert.url).netloc
        return mark_safe(f'<a href="{alert.url}" target="_blank">{domain}</a>')

    @admin.display(description="Teams")
    def _teams(self, alert: Alert):
        return ", ".join([team.slack_channel_name for team in alert.teams])

    @admin.action(description="Send selected alerts (test)")
    def send(self, request, queryset):
        count = 0
        alert: Alert
        for alert in queryset:
            count += alert.send(test=True)
        s = "" if count == 1 else "s"
        self.message_user(
            request,
            f"Successfully sent {count} test alert{s}.",
        )

    actions = [send]

    raw_id_fields = ("history",)
    readonly_fields = (
        "_message",
        "url",
        "_teams",
        "created_at",
    )
