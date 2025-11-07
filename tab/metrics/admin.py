from django.contrib import admin
from django.utils.safestring import mark_safe

from markdown import markdown

from .models import Alert, History, Subscription, Team


@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")

    list_display = (
        "id",
        "test__project",
        "test__name",
        "result",
        "failure_rate",
        "block_rate",
        "average_duration",
        "timestamp",
    )
    search_fields = (
        "test__project__repository",
        "test__name",
    )

    raw_id_fields = ("test", "result")
    readonly_fields = (
        "failure_rate",
        "block_rate",
        "average_duration",
        "timestamp",
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
        "project",
        "suite",
        "test",
        "primary",
    )
    list_filter = (
        "primary",
        "project",
        "suite",
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "history__test__project", "history__test__suite", "history__result"
            )
        )

    list_display = (
        "_message_text",
        "created_at",
        "_subscriptions",
        "sent_at",
    )
    list_filter = ("created_at", "sent_at")
    search_fields = (
        "history__test__project__repository",
        "history__test__name",
    )

    @admin.display(description="Message")
    def _message_text(self, alert: Alert):
        return alert.build()

    @admin.display(description="Message | HTML")
    def _message_html(self, alert: Alert):
        message = alert.build(debug=True)
        return mark_safe(message.html)

    @admin.display(description="Message | Markdown")
    def _message_markdown(self, alert: Alert):
        message = alert.build(debug=True)
        html = markdown(message.markdown, extensions=["fenced_code"])
        return mark_safe(html)

    @admin.display(description="Subscriptions")
    def _subscriptions(self, alert: Alert):
        return mark_safe("<br><br>".join([str(s) for s in alert.subscriptions]))

    @admin.action(description="Send selected alerts (debug)")
    def send(self, request, queryset):
        count = 0
        alert: Alert
        for alert in queryset:
            count += alert.send(debug=True)
        s = "" if count == 1 else "s"
        self.message_user(request, f"Successfully sent {count} test alert{s}.")

    actions = [send]

    raw_id_fields = ("test", "history")
    readonly_fields = (
        "_message_html",
        "_message_markdown",
        "created_at",
        "_subscriptions",
        "sent_at",
        "url",
    )
