from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("super-admin/dashboard/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("host/dashboard/", views.host_dashboard, name="host_dashboard"),
    path("end-user/dashboard/", views.end_user_dashboard, name="end_user_dashboard"),
    path("my-subscription/", views.my_subscription, name="my_subscription"),
    path("super-admin/subscriptions/", views.all_subscriptions, name="all_subscriptions"),
    path("super-admin/subscriptions/<int:subscription_id>/status/", views.update_subscription_status, name="update_subscription_status"),
    path("subscription/create-order/",views.create_subscription_order,name="create_subscription_order"),
    path("subscription/verify-payment/",views.verify_subscription_payment,name="verify_subscription_payment"),
    path("my-payment-receipts/",views.my_payment_receipts,name="my_payment_receipts"),
    path("payment-receipts/<int:payment_id>/download/",views.download_payment_receipt,name="download_payment_receipt"),
    path("payment-receipts/<int:payment_id>/resend/",views.resend_payment_receipt_email,name="resend_payment_receipt_email"),
]