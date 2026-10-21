from django.urls import path
from .views import (
    my_profile,
    create_profile,
    create_preferences,
    list_profiles,
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
]