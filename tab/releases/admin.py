from django.contrib import admin

from .models import Environment


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("project")

    search_fields = ("project__repository", "name", "url")
    list_display = (
        "id",
        "project",
        "url",
        "name",
        "created_at",
        "updated_at",
    )
    list_filter = ("name", "created_at", "updated_at", "project__repository")

    raw_id_fields = ("project",)
    readonly_fields = ("created_at", "updated_at")
