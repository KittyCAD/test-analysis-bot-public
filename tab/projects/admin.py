from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from .constants import RELEVANT_SAMPLES
from .models import Project, Result, Test


class LimitedInlineFormSet(BaseInlineFormSet):
    def get_queryset(self):
        return super().get_queryset()[:RELEVANT_SAMPLES]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    search_fields = ("repository",)
    list_display = ("name", "repository", "created_at", "updated_at")
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

    readonly_fields = ("created_at", "updated_at")

    class ResultInline(admin.TabularInline):
        model = Result
        formset = LimitedInlineFormSet
        can_delete = False
        max_num = 0

        verbose_name_plural = "Recent Results"
        fields = readonly_fields = (
            "branch",
            "_commit",
            "status",
            "duration",
            "target",
            "platform",
            "created_at",
        )

        @admin.display(description="Commit")
        def _commit(self, result: Result):
            return result.commit[:7]

        def get_queryset(self, request):
            test: Test = self.parent_model.objects.get(
                id=request.resolver_match.kwargs["object_id"]
            )
            return (
                super()
                .get_queryset(request)
                .filter(branch__in=test.relevant_branches)
                .order_by("-created_at")
                .select_related("test")
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
        "status",
        "duration",
        "target",
        "platform",
        "created_at",
    )
    ordering = ("-created_at",)
    list_filter = (
        "status",
        "target",
        "platform",
        "created_at",
        "test__project__repository",
        "branch",
    )

    @admin.display(description="Commit")
    def _commit(self, result: Result):
        return result.commit[:7]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")

    readonly_fields = ("created_at",)
