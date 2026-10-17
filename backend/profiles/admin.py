from django.contrib import admin
from .models import Profile
from .models import Profile, Preferences, ProfilePhoto, Match, CompatibilityScore

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "gender",
        "city",
        "profession",
        "created_at",
    )
    list_filter = ("gender", "city")
    search_fields = (
        "full_name",
        "user__username",
        "city",
        "profession",
    )


@admin.register(Preferences)
class PreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "min_age",
        "max_age",
        "preferred_city",
        "preferred_education",
    )
    list_filter = ("preferred_city",)
    search_fields = ("user__username", "preferred_city")

@admin.register(ProfilePhoto)
class ProfilePhotoAdmin(admin.ModelAdmin):
    list_display = (
        "profile",
        "image_url",
        "is_primary",
        "uploaded_at",
    )
    list_filter = ("is_primary",)
    search_fields = ("profile__full_name",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "sender",
        "receiver",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "sender__full_name",
        "receiver__full_name",
    )

@admin.register(CompatibilityScore)
class CompatibilityScoreAdmin(admin.ModelAdmin):
    list_display = ("profile_one", "profile_two", "score", "calculated_at")
    search_fields = ("profile_one__full_name", "profile_two__full_name")
    ordering = ("-score",)