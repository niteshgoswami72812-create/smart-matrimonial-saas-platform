
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.tenant_utils import get_user_tenant
from .models import Profile, Preferences
from .serializers import ProfileSerializer, PreferencesSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    tenant = get_user_tenant(request.user)

    return Response({
        "message": "Protected API accessed successfully!",
        "user_id": request.user.id,
        "username": request.user.username,
        "role": request.user.user_profile.role,
        "tenant": tenant.name if tenant else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_profile(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot create an end-user profile here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if Profile.objects.filter(user=request.user).exists():
        return Response(
            {"error": "A profile already exists for this user."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ProfileSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user, tenant=tenant)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_profiles(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        profiles = Profile.objects.all()
    else:
        profiles = Profile.objects.filter(tenant=tenant)

    serializer = ProfileSerializer(profiles, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_preferences(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot create end-user preferences here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if Preferences.objects.filter(user=request.user).exists():
        return Response(
            {"error": "Preferences already exist for this user."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PreferencesSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user, tenant=tenant)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
