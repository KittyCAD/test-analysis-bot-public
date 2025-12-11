from django.contrib import admin
from django.utils.safestring import mark_safe

from tab.projects.models import Result

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
        "_dependencies",
        "created_at",
        "updated_at",
    )
    list_filter = ("name", "created_at", "updated_at", "project__repository")

    raw_id_fields = ("project",)
    filter_horizontal = ("dependencies",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Dependencies")
    def _dependencies(self, environment: Environment):
        if environments := environment.dependencies.all():
            return ", ".join(str(e) for e in environments)
        return "-"


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):

    search_fields = ("environment__project__repository", "branch", "commit")
    list_display = (
        "id",
        "environment",
        "_branch",
        "_commit",
        "created_at",
        "tested_at",
        "results",
        "finalized_at",
    )
    list_filter = (
        "environment__name",
        "created_at",
        "tested_at",
        "finalized_at",
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

    @admin.action(description="Finalize selected releases")
    def finalize(self, request, queryset):
        count = 0
        release: Release
        for release in queryset:
            release.finalize()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(request, f"Successfully finalized {count} release{s}.")

    @admin.action(description="Reset selected releases")
    def reset(self, request, queryset):
        count = 0
        release: Release
        for release in queryset:
            release.results = 0
            release.tested_at = None
            release.finalized_at = None
            release.save()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(request, f"Successfully reset {count} release{s}.")

    actions = [finalize, reset]

    readonly_fields = ("health",)

    @admin.display(description="Project Health")
    def health(self, release: Release):
        return Result.objects.get_health(
            release.environment.project,
            release.commit,
            final=release.finalized_at is not None,
        )
