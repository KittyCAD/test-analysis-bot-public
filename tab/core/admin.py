from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email_domain",
        "repository_index",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "email_domain", "repository_index")
    list_filter = ("created_at", "updated_at")
    ordering = ("-created_at",)
