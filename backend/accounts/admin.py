from django.contrib import admin
from .models import UserProfile
from .models import UserProfile, Tenant
from .models import SubscriptionPlan, Subscription

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


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "max_profiles",
        "is_active",
    )
    list_filter = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "tenant",
        "plan",
        "status",
        "start_date",
        "end_date",
    )
    list_filter = ("status", "plan")
    search_fields = ("tenant__name",)