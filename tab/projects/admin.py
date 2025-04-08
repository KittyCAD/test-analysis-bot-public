from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("pk", "repository", "created_at", "updated_at")
    search_fields = ("repository",)
    list_filter = ("created_at", "updated_at")
