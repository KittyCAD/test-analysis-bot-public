from django.contrib import admin
from django.db.models import Q
from django.utils import timezone
from django.utils.timesince import timesince

from .models import Platform, Project, Result, Suite, Test


class SuiteInline(admin.TabularInline):
    model = Suite
    max_num = 0
    fields = ("name", "local_command", "supports_override")
    show_change_link = True


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
        "result_stale_threshold_humanized",
        "cleaned_at",
        "created_at",
        "updated_at",
    )
    ordering = ("repository",)
    list_filter = ("cleaned_at", "created_at", "updated_at")

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

    @admin.display(description="Results Stale")
    def result_stale_threshold_humanized(self, project: Project) -> str:
        if not project.result_stale_threshold:
            return "Never"
        return timesince(timezone.now() - project.result_stale_threshold)

    readonly_fields = ("cleaned_at", "created_at", "updated_at")
    inlines = [SuiteInline]


@admin.register(Suite)
class SuiteAdmin(admin.ModelAdmin):
    search_fields = ("project__repository", "name")
    list_display = ("id", "project", "name", "created_at", "updated_at")
    ordering = ("-updated_at",)
    list_filter = ("name",)

    readonly_fields = ("created_at", "updated_at")


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("project", "suite", "last_result")
        )

    search_fields = (
        "project__repository",
        "suite__name",
        "name",
        "disabled_user__email",
    )
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

    @admin.action(description="Disable selected tests")
    def disable(self, request, queryset):
        count = 0
        for test in queryset.filter(Q(disabled=False) | ~Q(disabled_platforms=[])):
            test.disabled = True
            test.disabled_platforms = []
            test.disabled_user = test.disabled_user or request.user
            test.save()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(
            request, f"Successfully marked {count} test{s} as non-blocking."
        )

    @admin.action(description=f"Disable selected tests on {Platform.MACOS.label}")
    def disable_macos(self, request, queryset):
        count = 0
        for test in queryset.exclude(disabled_platforms__contains=[Platform.MACOS]):
            test.disabled_platforms.append(Platform.MACOS)
            test.disabled_user = test.disabled_user or request.user
            test.save()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(
            request,
            f"Successfully marked {count} test{s} as non-blocking on {Platform.MACOS.label}.",
        )

    @admin.action(description=f"Disable selected tests on {Platform.WINDOWS.label}")
    def disable_windows(self, request, queryset):
        count = 0
        for test in queryset.exclude(disabled_platforms__contains=[Platform.WINDOWS]):
            test.disabled_platforms.append(Platform.WINDOWS)
            test.disabled_user = test.disabled_user or request.user
            test.save()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(
            request,
            f"Successfully marked {count} test{s} as non-blocking on {Platform.WINDOWS.label}.",
        )

    @admin.action(description="Enable selected tests")
    def enable(self, request, queryset):
        count = 0
        for test in queryset.filter(disabled=True):
            test.disabled = False
            test.disabled_platforms = []
            test.disabled_user = test.disabled_user or request.user
            test.save()
            count += 1
        s = "" if count == 1 else "s"
        self.message_user(
            request, f"Successfully enabled {count} test{s} to block merges."
        )

    actions = [disable, disable_macos, disable_windows, enable]

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

    def save_model(self, request, obj, form, change):
        if change and any(
            field in form.changed_data
            for field in [
                "disabled",
                "disabled_platform",
                "disabled_reason",
                "disabled_tracker",
            ]
        ):
            obj.disabled_user = obj.disabled_user or request.user
        super().save_model(request, obj, form, change)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")

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

    readonly_fields = ("markers", "created_at")
