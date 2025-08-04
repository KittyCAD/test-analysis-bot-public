from django.contrib import admin

from .models import History


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
