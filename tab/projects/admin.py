from django.contrib import admin

from .models import Project, Test


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("pk", "repository", "created_at", "updated_at")
    search_fields = ("repository",)
    list_filter = ("created_at", "updated_at")


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("pk", "project", "name", "created_at", "updated_at")
    search_fields = ("project__repository", "name")
    list_filter = ("created_at", "updated_at")
