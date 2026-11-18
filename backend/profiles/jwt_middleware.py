
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_token(raw_token):
    """
    Validate JWT access token and return an active Django user.
    """

    try:
        validated_token = AccessToken(raw_token)
    except TokenError:
        return AnonymousUser()

    user_id = validated_token.get("user_id")

    if not user_id:
        return AnonymousUser()

    User = get_user_model()

    try:
        return User.objects.get(
            pk=user_id,
            is_active=True,
        )
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Authenticate WebSocket connections using JWT access tokens.

    Expected WebSocket URL:
    ws://localhost:8000/ws/call/PROFILE_ID/?token=ACCESS_TOKEN
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):

        scope = dict(scope)

        query_string = scope.get(
            "query_string",
            b"",
        ).decode("utf-8")

        query_params = parse_qs(query_string)

        tokens = query_params.get("token", [])

        if tokens and tokens[0]:
            scope["user"] = await get_user_from_token(
                tokens[0]
            )
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(
            scope,
            receive,
            send,
        )
