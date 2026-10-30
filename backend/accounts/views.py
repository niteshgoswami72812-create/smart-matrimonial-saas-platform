from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .permissions import IsSuperAdmin, IsHost, IsEndUser
from .models import Subscription

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def super_admin_dashboard(request):
    return Response({
        "message": "Super Admin access granted",
        "role": request.user.user_profile.role,
    })


@api_view(["GET"])
@permission_classes([IsHost])
def host_dashboard(request):
    return Response({
        "message": "Host access granted",
        "role": request.user.user_profile.role,
    })


@api_view(["GET"])
@permission_classes([IsEndUser])
def end_user_dashboard(request):
    return Response({
        "message": "End User access granted",
        "role": request.user.user_profile.role,
    })

from rest_framework.permissions import IsAuthenticated
from .models import Subscription


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    try:
        user_profile = request.user.user_profile
    except Exception:
        return Response(
            {"error": "User profile not found."},
            status=404,
        )

    if not user_profile.tenant:
        return Response(
            {"error": "No tenant assigned to this user."},
            status=404,
        )

    subscription = (
        Subscription.objects
        .filter(tenant=user_profile.tenant)
        .select_related("plan", "tenant")
        .order_by("-created_at")
        .first()
    )

    if not subscription:
        return Response(
            {"error": "No subscription found for this tenant."},
            status=404,
        )

    return Response({
        "tenant": subscription.tenant.name,
        "plan": subscription.plan.name,
        "price": str(subscription.plan.price),
        "status": subscription.status,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "max_profiles": subscription.plan.max_profiles,
    })


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def all_subscriptions(request):
    subscriptions = (
        Subscription.objects
        .select_related("tenant", "plan")
        .order_by("-created_at")
    )

    data = [
        {
            "id": subscription.id,
            "tenant": subscription.tenant.name,
            "plan": subscription.plan.name,
            "price": str(subscription.plan.price),
            "status": subscription.status,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "max_profiles": subscription.plan.max_profiles,
        }
        for subscription in subscriptions
    ]

    return Response(data)


@api_view(["PATCH"])
@permission_classes([IsSuperAdmin])
def update_subscription_status(request, subscription_id):
    allowed_statuses = ["pending", "active", "expired", "cancelled"]
    new_status = request.data.get("status")

    if new_status not in allowed_statuses:
        return Response(
            {
                "error": "Invalid status.",
                "allowed_statuses": allowed_statuses,
            },
            status=400,
        )

    try:
        subscription = Subscription.objects.select_related(
            "tenant", "plan"
        ).get(id=subscription_id)
    except Subscription.DoesNotExist:
        return Response(
            {"error": "Subscription not found."},
            status=404,
        )

    subscription.status = new_status
    subscription.save(update_fields=["status", "updated_at"])

    return Response({
        "message": "Subscription status updated successfully.",
        "id": subscription.id,
        "tenant": subscription.tenant.name,
        "plan": subscription.plan.name,
        "status": subscription.status,
    })

