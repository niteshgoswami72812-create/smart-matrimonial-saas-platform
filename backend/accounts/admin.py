from django.contrib import admin
from .models import UserProfile
from .models import UserProfile, Tenant

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "tenant", "created_at", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "contact_email",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "contact_email")
    prepopulated_fields = {"slug": ("name",)}
