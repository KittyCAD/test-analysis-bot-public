from django.contrib import admin

from .models import Project, Result, Test


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "repository", "created_at", "updated_at")
    search_fields = ("repository",)
    list_filter = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project", "created_at", "updated_at")
    search_fields = ("project__repository", "name")
    list_filter = ("created_at", "updated_at")
    ordering = ("-updated_at",)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    @admin.display(description="Project")
    def get_project(self, result: Result):
        return result.test.project

    list_display = ("id", "status", "test", "test__project", "created_at")
    search_fields = ("test__project__repository", "test__name")
    list_filter = ("status", "created_at")
    ordering = ("-created_at",)
