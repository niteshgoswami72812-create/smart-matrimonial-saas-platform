
from rest_framework.permissions import BasePermission


class HasUserProfileRole(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        user_profile = getattr(user, "user_profile", None)

        if user_profile is None:
            return False

        return user_profile.role in self.allowed_roles


class IsSuperAdmin(HasUserProfileRole):
    allowed_roles = ("super_admin",)


class IsHost(HasUserProfileRole):
    allowed_roles = ("host",)


class IsEndUser(HasUserProfileRole):
    allowed_roles = ("end_user",)


class IsSuperAdminOrHost(HasUserProfileRole):
    allowed_roles = ("super_admin", "host")
