from django.urls import path
from . import views

urlpatterns = [
    path("super-admin/dashboard/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("host/dashboard/", views.host_dashboard, name="host_dashboard"),
    path("end-user/dashboard/", views.end_user_dashboard, name="end_user_dashboard"),
    path("my-subscription/", views.my_subscription, name="my_subscription"),
    path("super-admin/subscriptions/", views.all_subscriptions, name="all_subscriptions"),
    path("super-admin/subscriptions/<int:subscription_id>/status/",views.update_subscription_status,name="update_subscription_status"),
]