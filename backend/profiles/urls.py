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
    upload_profile_photo,
    my_profile_photos,
    matched_profile_photos,
    delete_profile_photo,
    subscription_plans,
    upload_photo_post,
    photo_posts_feed,
    delete_photo_post,
    chat_messages,
    block_profile,
    list_blocked_profiles,
    unfriend_profile,
    remove_connection,
)

urlpatterns = [
    # Profile
    path("me/", my_profile, name="my-profile"),
    path("create/", create_profile, name="create-profile"),
    path("list/", list_profiles, name="list-profiles"),
    path(
        "me/detail/",
        my_profile_detail,
        name="my-profile-detail",
    ),

    # Preferences
    path(
        "preferences/create/",
        create_preferences,
        name="create-preferences",
    ),
    path(
        "preferences/me/",
        my_preferences_detail,
        name="my-preferences-detail",
    ),

    # Match System
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

    # Compatibility Score
    path(
        "compatibility/<int:profile_id>/",
        calculate_profile_compatibility,
        name="calculate-profile-compatibility",
    ),

    # AI Match Explanation
    path(
        "match-explanation/<int:profile_id>/",
        generate_profile_match_explanation,
        name="generate-profile-match-explanation",
    ),

    # Profile Photos
    path(
        "photos/upload/",
        upload_profile_photo,
        name="upload-profile-photo",
    ),
    path(
        "photos/me/",
        my_profile_photos,
        name="my-profile-photos",
    ),
    path(
        "photos/<int:profile_id>/",
        matched_profile_photos,
        name="matched-profile-photos",
    ),
    path(
        "photos/<int:photo_id>/delete/",
        delete_profile_photo,
        name="delete-profile-photo",
    ),

    # Subscription Plans
    path(
        "subscription-plans/",
        subscription_plans,
        name="subscription-plans",
    ),

    # Photo Posts
    path(
        "posts/upload/",
        upload_photo_post,
        name="upload-photo-post",
    ),
    path(
        "posts/feed/",
        photo_posts_feed,
        name="photo-posts-feed",
    ),
    path(
        "posts/<int:post_id>/delete/",
        delete_photo_post,
        name="delete-photo-post",
    ),

    # Chat
    path(
        "chat/<int:profile_id>/",
        chat_messages,
        name="chat-messages",
    ),

    path(
        "blocks/",
        list_blocked_profiles,
        name="list-blocked-profiles",
    ),
    path(
        "blocks/<int:profile_id>/",
        block_profile,
        name="block-profile",
    ),
    path(
        "matches/<int:profile_id>/unfriend/",
        unfriend_profile,
        name="unfriend-profile",
    ),
    path(
        "matches/<int:profile_id>/remove/",
        remove_connection,
        name="remove-connection",
    ),

]