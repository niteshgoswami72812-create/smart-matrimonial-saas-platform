
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import IsSuperAdmin, IsHost, IsEndUser


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
