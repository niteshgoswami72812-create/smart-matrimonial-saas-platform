from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied

def get_user_tenant(user):
    """
    Return the tenant assigned to the authenticated user.
    Super Admin is not assigned a tenant by default.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")

    try:
        user_profile = user.user_profile
    except ObjectDoesNotExist:
        raise PermissionDenied("User profile is not configured.")

    if user_profile.role == "super_admin":
        return None

    if user_profile.tenant_id is None:
        raise PermissionDenied("No tenant is assigned to this user.")

    if not user_profile.tenant.is_active:
        raise PermissionDenied("This tenant is inactive.")

    return user_profile.tenant
