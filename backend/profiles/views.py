
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    return Response({
        "message": "Protected API accessed successfully!",
        "user_id": request.user.id,
        "username": request.user.username,
    })
