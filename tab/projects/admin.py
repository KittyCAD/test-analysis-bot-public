from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import Project, Result, Test


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    search_fields = ("repository", "error_indicators")
    list_display = (
        "name",
        "repository",
        "default_branch",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    list_filter = ("created_at", "updated_at")

    readonly_fields = ("created_at", "updated_at")


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

    readonly_fields = ("last_result", "markers", "created_at", "updated_at")

    class ResultInline(admin.TabularInline):
        model = Result
        show_change_link = True
        can_delete = False
        max_num = 0
        classes = ("collapse",)

        verbose_name_plural = "Recent Results"
        fields = readonly_fields = (
            "status",
            "branch",
            "_commit",
            "target",
            "platform",
            "duration",
            "created_at",
        )

        @admin.display(description="Commit")
        def _commit(self, result: Result):
            return result.commit_humanized

        def get_queryset(self, request):
            test_id = request.resolver_match.kwargs.get("object_id")
            if not test_id:
                return super().get_queryset(request)
            test: Test = self.parent_model.objects.get(id=test_id)
            limit = timezone.now() - timedelta(days=1)
            return (
                super()
                .get_queryset(request)
                .filter(
                    branch__in=test.relevant_branches,
                    created_at__gte=limit,
                )
            )

    inlines = (ResultInline,)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    search_fields = ("test__project__repository", "test__name", "branch", "commit")
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
