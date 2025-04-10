from django.contrib import admin

from .models import Project, Result, Test


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "repository", "created_at", "updated_at")
    search_fields = ("repository",)
    list_filter = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "created_at", "updated_at")
    search_fields = ("project__repository", "name")
    list_filter = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "test__project",
        "test__name",
        "status",
        "branch",
        "created_at",
    )
    search_fields = ("test__project__repository", "test__name", "branch", "commit")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("test__project")
