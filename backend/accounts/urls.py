
from django.urls import path
from . import views

urlpatterns = [
    path(
        "super-admin/dashboard/",
        views.super_admin_dashboard,
        name="super_admin_dashboard",
    ),
    path(
        "host/dashboard/",
        views.host_dashboard,
        name="host_dashboard",
    ),
    path(
        "end-user/dashboard/",
        views.end_user_dashboard,
        name="end_user_dashboard",
    ),
]
