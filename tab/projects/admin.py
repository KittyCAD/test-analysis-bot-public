from django.contrib import admin
from django.utils import timezone
from django.utils.timesince import timesince

from .models import Project, Result, Test


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    search_fields = ("repository", "error_indicators")
    list_display = (
        "name",
        "repository",
        "default_branch",
        "branch_inactive_threshold_humanized",
        "test_inactive_threshold_humanized",
        "test_stale_threshold_humanized",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    list_filter = ("created_at", "updated_at")

    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Branches Inactive")
    def branch_inactive_threshold_humanized(self, project: Project) -> str:
        if not project.branch_inactive_threshold:
            return "Never"
        return timesince(timezone.now() - project.branch_inactive_threshold)

    @admin.display(description="Tests Inactive")
    def test_inactive_threshold_humanized(self, project: Project) -> str:
        if not project.test_inactive_threshold:
            return "Never"
        return timesince(timezone.now() - project.test_inactive_threshold)

    @admin.display(description="Tests Stale")
    def test_stale_threshold_humanized(self, project: Project) -> str:
        if not project.test_stale_threshold:
            return "Never"
        return timesince(timezone.now() - project.test_stale_threshold)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    search_fields = ("project__repository", "name")
    list_display = (
        "id",
        "project",
        "name",
        "markers",
        "enabled",
        "failure_rate",
        "block_rate",
        "average_duration",
        "original_branch",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    list_filter = (
        "enabled",
        "created_at",
        "updated_at",
        "project__repository",
        "original_branch",
    )

    readonly_fields = (
        "enabled",
        "significant_branches",
        "failure_rate",
        "block_rate",
        "average_duration",
        "last_result",
        "markers",
        "created_at",
        "updated_at",
    )


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    search_fields = (
        "test__project__repository",
        "test__name",
        "branch",
        "commit",
        "message",
    )
    list_display = (
        "id",
        "test__project",
        "test__name",
        "branch",
        "_commit",
        "target",
        "platform",
        "final",
        "status",
        "duration",
        "markers",
        "created_at",
    )
    list_filter = (
        "status",
        "target",
        "platform",
        "final",
        "created_at",
        "test__project__repository",
        "branch",
    )

    @admin.display(description="Commit")
    def _commit(self, result: Result):
        return result.commit_humanized

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")

    readonly_fields = ("markers", "created_at")
