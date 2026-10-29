
from django.urls import path
from .views import (
    my_profile,
    my_profile_detail,
    my_preferences_detail,
    create_profile,
    create_preferences,
    list_profiles,
    send_match_request,
    list_matches,
    update_match_status,
    calculate_profile_compatibility,
    generate_profile_match_explanation,
)

urlpatterns = [
    path("me/", my_profile, name="my-profile"),
    path("create/", create_profile, name="create-profile"),
    path("list/", list_profiles, name="list-profiles"),

    path(
        "preferences/create/",
        create_preferences,
        name="create-preferences",
    ),
    path(
        "me/detail/",
        my_profile_detail,
        name="my-profile-detail",
    ),
    path(
        "preferences/me/",
        my_preferences_detail,
        name="my-preferences-detail",
    ),

    # Task 16: Match System
    path(
        "matches/send/",
        send_match_request,
        name="send-match-request",
    ),
    path(
        "matches/",
        list_matches,
        name="list-matches",
    ),
    path(
        "matches/<int:match_id>/status/",
        update_match_status,
        name="update-match-status",
    ),

    # Stage 17: Compatibility Score
    path(
        "compatibility/<int:profile_id>/",
        calculate_profile_compatibility,
        name="calculate-profile-compatibility",
    ),
    # Stage 18: AI Match Explanation
     path(
         "match-explanation/<int:profile_id>/",
         generate_profile_match_explanation,
         name="generate-profile-match-explanation"
         ),
]
