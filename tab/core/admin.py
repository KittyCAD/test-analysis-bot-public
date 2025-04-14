from django.contrib import admin, messages

from .models import Organization, generate_key


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    search_fields = ("name", "email_domain", "repository_index")
    actions = ["regenerate_key"]
    list_display = (
        "name",
        "email_domain",
        "repository_index",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    list_filter = ("created_at", "updated_at")

    @admin.action(description="Regenerate key for selected organizations")
    def regenerate_key(self, request, queryset):
        for organization in queryset:
            organization.key = generate_key()
            organization.save()
        count = queryset.count()
        s = "" if count == 1 else "s"
        self.message_user(
            request,
            f"Successfully regenerated keys for {count} organization{s}.",
            messages.SUCCESS,
        )

    readonly_fields = ("created_at", "updated_at")
