from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import Environment, Release


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


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):

    search_fields = ()
    list_display = (
        "id",
        "environment",
        "_branch",
        "_commit",
        "created_at",
        "results_passed",
        "results_total",
        "tested_at",
    )
    list_filter = (
        "environment__name",
        "created_at",
        "tested_at",
        "environment__project__repository",
    )

    @admin.display(description="Branch")
    def _branch(self, release: Release):
        return mark_safe(
            f'<a href="{release.branch_url}" target="_blank">{release.branch}</a>'
        )

    @admin.display(description="Commit")
    def _commit(self, release: Release):
        return mark_safe(
            f'<a href="{release.commit_url}" target="_blank">{release.commit_humanized}</a>'
        )
