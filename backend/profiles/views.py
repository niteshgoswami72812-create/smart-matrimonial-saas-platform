from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import cloudinary.uploader


from rest_framework.parsers import MultiPartParser, FormParser
from accounts.models import SubscriptionPlan, Subscription
from accounts.tenant_utils import get_user_tenant
from django.utils import timezone
from .models import (
    Profile,
    Preferences,
    Match,
    CompatibilityScore,
    AIMatchExplanation,
    ProfilePhoto,
    PhotoPost,
    Message,
    ProfileBlock,
    RemovedProfile,
)

from .serializers import (
    ProfileSerializer,
    PreferencesSerializer,
    MatchSerializer,
    AIMatchExplanationSerializer,
    ProfilePhotoSerializer,
    PhotoPostSerializer,
    MessageSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
)

from datetime import date
from decimal import Decimal



def calculate_compatibility_score(profile_one, profile_two):
    """Calculate compatibility using both users' profile details."""

    today = date.today()
    score = 0

    # 1. Age compatibility — 30 points
    if profile_one.date_of_birth and profile_two.date_of_birth:

        age_one = (
            today.year
            - profile_one.date_of_birth.year
            - (
                (today.month, today.day)
                < (
                    profile_one.date_of_birth.month,
                    profile_one.date_of_birth.day,
                )
            )
        )

        age_two = (
            today.year
            - profile_two.date_of_birth.year
            - (
                (today.month, today.day)
                < (
                    profile_two.date_of_birth.month,
                    profile_two.date_of_birth.day,
                )
            )
        )

        age_difference = abs(age_one - age_two)

        if age_difference <= 2:
            score += 30
        elif age_difference <= 5:
            score += 25
        elif age_difference <= 8:
            score += 18
        elif age_difference <= 12:
            score += 10

    # 2. City compatibility — 20 points
    city_one = (profile_one.city or "").strip().casefold()
    city_two = (profile_two.city or "").strip().casefold()

    if city_one and city_two and city_one == city_two:
        score += 20

    # 3. Education compatibility — 25 points
    education_one = (
        profile_one.education or ""
    ).strip().casefold()

    education_two = (
        profile_two.education or ""
    ).strip().casefold()

    if (
        education_one
        and education_two
        and education_one == education_two
    ):
        score += 25

    # 4. Profession compatibility — 25 points
    profession_one = (
        profile_one.profession or ""
    ).strip().casefold()

    profession_two = (
        profile_two.profession or ""
    ).strip().casefold()

    if (
        profession_one
        and profession_two
        and profession_one == profession_two
    ):
        score += 25

    return round(score, 2)

def is_profile_blocked(profile_one, profile_two, tenant):
    return ProfileBlock.objects.filter(
        tenant=tenant
    ).filter(
        Q(
            blocker=profile_one,
            blocked=profile_two,
        )
        |
        Q(
            blocker=profile_two,
            blocked=profile_one,
        )
    ).exists()

def generate_match_explanation(profile, preferences, score):
    """Generate a preference-based explanation for a potential match."""
    from datetime import date

    reasons = []

    # Age preference
    if profile.date_of_birth:
        today = date.today()
        age = (
            today.year
            - profile.date_of_birth.year
            - (
                (today.month, today.day)
                < (
                    profile.date_of_birth.month,
                    profile.date_of_birth.day,
                )
            )
        )

        if preferences.min_age <= age <= preferences.max_age:
            reasons.append(
                f"Age preference matches. Profile age is {age}."
            )
        else:
            reasons.append(
                f"Age preference does not match. Profile age is {age}."
            )

    # City preference
    if preferences.preferred_city.strip():
        if (
            profile.city.strip().casefold()
            == preferences.preferred_city.strip().casefold()
        ):
            reasons.append(
                f"Preferred city matches: {profile.city}."
            )
        else:
            reasons.append(
                f"Preferred city differs. Preferred: "
                f"{preferences.preferred_city}; profile city: "
                f"{profile.city or 'Not specified'}."
            )

    # Education preference
    if preferences.preferred_education.strip():
        if (
            profile.education.strip().casefold()
            == preferences.preferred_education.strip().casefold()
        ):
            reasons.append("Education preference matches.")
        else:
            reasons.append("Education preference does not match.")

    # Profession preference
    if preferences.preferred_profession.strip():
        if (
            profile.profession.strip().casefold()
            == preferences.preferred_profession.strip().casefold()
        ):
            reasons.append("Profession preference matches.")
        else:
            reasons.append("Profession preference does not match.")

    if not reasons:
        summary = (
            "Not enough profile information or saved preferences "
            "to explain this match."
        )
    elif score >= 80:
        summary = (
            "This profile is a strong potential match based on "
            "your saved preferences."
        )
    elif score >= 60:
        summary = (
            "This profile is a moderate potential match based on "
            "your saved preferences."
        )
    elif score > 0:
        summary = (
            "This profile has limited alignment with your "
            "saved preferences."
        )
    else:
        summary = (
            "This profile does not currently match the evaluated "
            "preferences."
        )

    return {
        "summary": summary,
        "reasons": reasons,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_profile_match_explanation(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot generate match explanations here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before generating an explanation."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Target profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if current_profile.id == target_profile.id:
        return Response(
            {
                "error": (
                    "You cannot explain compatibility with your own profile."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        preferences = Preferences.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Preferences.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your preferences before generating an explanation."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    compatibility = CompatibilityScore.objects.filter(
        profile_one=current_profile,
        profile_two=target_profile,
    ).first()

    if compatibility is None:
        return Response(
            {
                "error": (
                    "Calculate compatibility first using the "
                    "Compatibility Score API."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    explanation_data = generate_match_explanation(
        target_profile,
        preferences,
        float(compatibility.score),
    )

    explanation, _ = AIMatchExplanation.objects.update_or_create(
        compatibility=compatibility,
        defaults={
            "summary": explanation_data["summary"],
            "reasons": explanation_data["reasons"],
        },
    )

    return Response(
        {
            "profile_id": target_profile.id,
            "profile_name": target_profile.full_name,
            "compatibility_score": str(compatibility.score),
            "match_explanation": AIMatchExplanationSerializer(
                explanation
            ).data,
        },
        status=status.HTTP_200_OK,
    )


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
            {
                "error": (
                    "Super Admin cannot create an end-user profile here."
                )
            },
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
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_profiles(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        profiles = Profile.objects.all()

    else:
        try:
            current_profile = Profile.objects.get(
                user=request.user,
                tenant=tenant,
            )
        except Profile.DoesNotExist:
            return Response(
                {
                    "error": (
                        "Create your profile before discovering profiles."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        profiles = Profile.objects.filter(
            tenant=tenant
        ).exclude(
            id=current_profile.id
        )

        # Male users see female profiles.
        if current_profile.gender == "male":
            profiles = profiles.filter(gender="female")

        # Female users see male profiles.
        elif current_profile.gender == "female":
            profiles = profiles.filter(gender="male")

        # Hide profiles blocked by the current user.
        blocked_by_current = ProfileBlock.objects.filter(
            tenant=tenant,
            blocker=current_profile,
        ).values_list("blocked_id", flat=True)

        # Hide profiles that have blocked the current user.
        blocked_current = ProfileBlock.objects.filter(
            tenant=tenant,
            blocked=current_profile,
        ).values_list("blocker_id", flat=True)

        profiles = profiles.exclude(
            id__in=blocked_by_current
        ).exclude(
            id__in=blocked_current
        )

    serializer = ProfileSerializer(profiles.distinct(), many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def calculate_profile_compatibility(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot calculate end-user compatibility here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before calculating compatibility."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Target profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if current_profile.id == target_profile.id:
        return Response(
            {
                "error": (
                    "You cannot calculate compatibility with your own profile."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Calculate score using both users' profiles
    score = calculate_compatibility_score(
        current_profile,
        target_profile,
    )

    # Keep the profile pair in a consistent order
    profile_one, profile_two = sorted(
        (current_profile, target_profile),
        key=lambda profile: profile.id,
    )

    print(
        "DEBUG COMPATIBILITY:",
        request.user.username,
        profile_one.id,
        profile_two.id,
        score,
    )

    compatibility, _ = CompatibilityScore.objects.update_or_create(
        profile_one=profile_one,
        profile_two=profile_two,
        defaults={"score": Decimal(str(score))},
    )

    return Response(
        {
            "profile_id": target_profile.id,
            "profile_name": target_profile.full_name,
            "compatibility_score": str(compatibility.score),
            "calculated_at": compatibility.calculated_at,
        },
        status=status.HTTP_200_OK,
    )

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def my_profile_detail(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin does not have an end-user profile here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Profile not found. Please create your profile first."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(ProfileSerializer(profile).data)

    serializer = ProfileSerializer(
        profile,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def my_preferences_detail(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin does not have end-user preferences here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        preferences = Preferences.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Preferences.DoesNotExist:
        return Response(
            {
                "error": (
                    "Preferences not found. Please create preferences first."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(PreferencesSerializer(preferences).data)

    serializer = PreferencesSerializer(
        preferences,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


# Task 16: Send a match request

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_match_request(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot send match requests."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        sender = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before sending a match request."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    receiver_id = request.data.get("receiver")

    if receiver_id is None:
        return Response(
            {"error": "Receiver profile ID is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        receiver = Profile.objects.get(
            id=receiver_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Receiver profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Prevent sending a request to your own profile
    if sender.pk == receiver.pk:
        return Response(
            {
                "error": (
                    "You cannot send a match request to your own profile."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Prevent match requests between blocked profiles
    if is_profile_blocked(sender, receiver, tenant):
        return Response(
            {
                "error": (
                    "You cannot send a match request to this profile."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        match, created = Match.objects.get_or_create(
            sender=sender,
            receiver=receiver,
        )
    except IntegrityError:
        return Response(
            {"error": "A duplicate match request already exists."},
            status=status.HTTP_409_CONFLICT,
        )

    if not created:
        return Response(
            {
                "error": (
                    "You have already sent a request to this profile."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        MatchSerializer(match).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def block_profile(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot block profiles."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if current_profile.pk == target_profile.pk:
        return Response(
            {"error": "You cannot block your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Unblock profile
    if request.method == "DELETE":
        deleted_count, _ = ProfileBlock.objects.filter(
            blocker=current_profile,
            blocked=target_profile,
            tenant=tenant,
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": "This profile is not blocked by you."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"message": "Profile unblocked successfully."},
            status=status.HTTP_200_OK,
        )

    # Block profile and end existing connections
    with transaction.atomic():
        block, created = ProfileBlock.objects.get_or_create(
            blocker=current_profile,
            blocked=target_profile,
            tenant=tenant,
        )

        Match.objects.filter(
            Q(sender=current_profile, receiver=target_profile)
            | Q(sender=target_profile, receiver=current_profile)
        ).delete()

        RemovedProfile.objects.filter(
            tenant=tenant,
        ).filter(
            Q(owner=current_profile, removed_profile=target_profile)
            | Q(owner=target_profile, removed_profile=current_profile)
        ).delete()

    if not created:
        return Response(
            {"message": "This profile is already blocked."},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"message": "Profile blocked successfully."},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_blocked_profiles(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin does not have blocked profiles."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    blocked_profiles = (
        ProfileBlock.objects
        .filter(
            blocker=current_profile,
            tenant=tenant,
        )
        .select_related("blocked")
        .order_by("-created_at")
    )

    data = [
        {
            "profile_id": block.blocked.id,
            "full_name": block.blocked.full_name,
            "blocked_at": block.created_at,
        }
        for block in blocked_profiles
    ]

    return Response(
        {
            "count": len(data),
            "blocked_profiles": data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def unfriend_profile(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot unfriend profiles."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if current_profile.pk == target_profile.pk:
        return Response(
            {"error": "You cannot unfriend your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    accepted_match_exists = Match.objects.filter(
        Q(sender=current_profile, receiver=target_profile)
        | Q(sender=target_profile, receiver=current_profile),
        status="accepted",
    ).exists()

    if not accepted_match_exists:
        return Response(
            {"error": "No accepted connection exists with this profile."},
            status=status.HTTP_404_NOT_FOUND,
        )

    with transaction.atomic():
        Match.objects.filter(
            Q(sender=current_profile, receiver=target_profile)
            | Q(sender=target_profile, receiver=current_profile)
        ).delete()

        RemovedProfile.objects.filter(
            tenant=tenant,
        ).filter(
            Q(owner=current_profile, removed_profile=target_profile)
            | Q(owner=target_profile, removed_profile=current_profile)
        ).delete()

    return Response(
        {"message": "Profile unfriended successfully."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def remove_connection(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot remove connections."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile first."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {"error": "Profile not found in your tenant."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if current_profile.pk == target_profile.pk:
        return Response(
            {"error": "You cannot remove your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if is_profile_blocked(current_profile, target_profile, tenant):
        return Response(
            {"error": "This connection is blocked."},
            status=status.HTTP_403_FORBIDDEN,
        )

    accepted_match_exists = Match.objects.filter(
        Q(sender=current_profile, receiver=target_profile)
        | Q(sender=target_profile, receiver=current_profile),
        status="accepted",
    ).exists()

    if not accepted_match_exists:
        return Response(
            {"error": "No accepted connection exists with this profile."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Restore removed connection
    if request.method == "DELETE":
        deleted_count, _ = RemovedProfile.objects.filter(
            owner=current_profile,
            removed_profile=target_profile,
            tenant=tenant,
        ).delete()

        if deleted_count == 0:
            return Response(
                {"error": "This profile is not in your removed list."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"message": "Connection restored successfully."},
            status=status.HTTP_200_OK,
        )

    # Hide connection only from current user's list
    removed, created = RemovedProfile.objects.get_or_create(
        owner=current_profile,
        removed_profile=target_profile,
        tenant=tenant,
    )

    if not created:
        return Response(
            {"message": "This connection is already removed."},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"message": "Connection removed successfully."},
        status=status.HTTP_201_CREATED,
    )



# Task 16: List sent and received match requests
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_matches(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot access end-user match requests here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before viewing match requests."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get profiles removed by the current user.
    removed_profile_ids = RemovedProfile.objects.filter(
        tenant=tenant,
        owner=profile,
    ).values_list(
        "removed_profile_id",
        flat=True,
    )

    matches = Match.objects.filter(
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).filter(
        Q(sender=profile) | Q(receiver=profile)
    ).exclude(
        Q(
            sender=profile,
            receiver_id__in=removed_profile_ids,
        ) |
        Q(
            receiver=profile,
            sender_id__in=removed_profile_ids,
        )
    ).select_related(
        "sender",
        "receiver",
    ).order_by("-created_at")

    return Response(MatchSerializer(matches, many=True).data)

# Task 16: Accept or reject a received match request
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_match_status(request, match_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot update end-user match requests."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Profile not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_status = request.data.get("status")

    if new_status not in ("accepted", "rejected"):
        return Response(
            {
                "error": (
                    "Status must be either 'accepted' or 'rejected'."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        match = Match.objects.get(
            id=match_id,
            receiver=profile,
            receiver__tenant=tenant,
            sender__tenant=tenant,
        )
    except Match.DoesNotExist:
        return Response(
            {"error": "Received match request not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if match.status != "pending":
        return Response(
            {
                "error": (
                    "Only pending match requests can be updated."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    match.status = new_status
    match.save(update_fields=["status", "updated_at"])

    return Response(
        MatchSerializer(match).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_preferences(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot create end-user preferences here."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if Preferences.objects.filter(user=request.user).exists():
        return Response(
            {
                "error": (
                    "Preferences already exist for this user."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = PreferencesSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save(
            user=request.user,
            tenant=tenant,
        )
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


# Stage 20: Cloudinary Profile Photo Upload
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_profile_photo(request):
    image = request.FILES.get("image")

    if not image:
        return Response(
            {
                "error": (
                    "Please upload an image using the 'image' field."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    if image.content_type not in allowed_types:
        return Response(
            {
                "error": (
                    "Only JPG, PNG and WEBP images are allowed."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if image.size > 5 * 1024 * 1024:
        return Response(
            {
                "error": (
                    "Image size must not exceed 5 MB."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    profile = Profile.objects.filter(
        user=request.user,
        tenant=tenant,
    ).first()

    if not profile:
        return Response(
            {
                "error": (
                    "Create your profile before uploading a photo."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    is_primary = str(
        request.data.get("is_primary", "false")
    ).lower() in ("true", "1", "yes")

    try:
        upload_result = cloudinary.uploader.upload(
            image,
            folder="smart-matrimonial-saas/profile-photos",
            resource_type="image",
        )

        if is_primary:
            ProfilePhoto.objects.filter(
                profile=profile,
                is_primary=True,
            ).update(is_primary=False)

        photo = ProfilePhoto.objects.create(
            profile=profile,
            image_url=upload_result["secure_url"],
            image_public_id=upload_result["public_id"],
            is_primary=is_primary,
        )

    except Exception as e:
        print("Cloudinary profile photo error:", repr(e))
        return Response(
            {
                "error": (
                    "Image upload failed. Please try again."
                )
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        ProfilePhotoSerializer(photo).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_profile_photos(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Profile not found. Please create your profile first."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    photos = ProfilePhoto.objects.filter(
        profile=profile
    ).order_by(
        "-is_primary",
        "-uploaded_at",
    )

    serializer = ProfilePhotoSerializer(
        photos,
        many=True,
    )

    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def matched_profile_photos(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        my_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Your profile was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        target_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Profile not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    accepted_match = Match.objects.filter(
        Q(
            sender=my_profile,
            receiver=target_profile,
        )
        |
        Q(
            sender=target_profile,
            receiver=my_profile,
        ),
        status="accepted",
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).exists()

    if not accepted_match:
        return Response(
            {
                "error": (
                    "You can view photos only after accepting a match."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    photos = ProfilePhoto.objects.filter(
        profile=target_profile
    ).order_by(
        "-is_primary",
        "-uploaded_at",
    )

    serializer = ProfilePhotoSerializer(
        photos,
        many=True,
    )

    return Response(serializer.data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_profile_photo(request, photo_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Your profile was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        photo = ProfilePhoto.objects.get(
            id=photo_id,
            profile=profile,
            profile__tenant=tenant,
        )
    except ProfilePhoto.DoesNotExist:
        return Response(
            {
                "error": (
                    "Photo not found or you cannot delete this photo."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Delete the Cloudinary image when its public_id is available.
    if photo.image_public_id:
        try:
            result = cloudinary.uploader.destroy(
                photo.image_public_id,
                resource_type="image",
            )

            if result.get("result") not in ("ok", "not found"):
                return Response(
                    {
                        "error": (
                            "Could not delete the image from storage."
                        )
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception as e:
            print("Cloudinary delete error:", repr(e))
            return Response(
                {
                    "error": (
                        "Image deletion failed. Please try again."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

    was_primary = photo.is_primary
    photo.delete()

    # Promote the latest remaining photo if primary was deleted.
    if was_primary:
        next_photo = ProfilePhoto.objects.filter(
            profile=profile
        ).order_by("-uploaded_at").first()

        if next_photo:
            next_photo.is_primary = True
            next_photo.save(update_fields=["is_primary"])

    return Response(
        {"message": "Profile photo deleted successfully."},
        status=status.HTTP_200_OK,
    )


# Photo Posts: Upload, Feed and Delete
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_photo_post(request):
    image = request.FILES.get("image")
    caption = request.data.get("caption", "")

    if not image:
        return Response(
            {
                "error": (
                    "Please upload an image using the 'image' field."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    if image.content_type not in allowed_types:
        return Response(
            {
                "error": (
                    "Only JPG, PNG and WEBP images are allowed."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if image.size > 5 * 1024 * 1024:
        return Response(
            {
                "error": (
                    "Image size must not exceed 5 MB."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(caption) > 500:
        return Response(
            {
                "error": (
                    "Caption cannot exceed 500 characters."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    profile = Profile.objects.filter(
        user=request.user,
        tenant=tenant,
    ).first()

    if not profile:
        return Response(
            {
                "error": (
                    "Create your profile before posting."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        upload_result = cloudinary.uploader.upload(
            image,
            folder="smart-matrimonial-saas/photo-posts",
            resource_type="image",
        )

        post = PhotoPost.objects.create(
            profile=profile,
            image_url=upload_result["secure_url"],
            image_public_id=upload_result["public_id"],
            caption=caption,
        )

    except Exception as e:
        print("Photo post upload error:", repr(e))
        return Response(
            {
                "error": (
                    "Post upload failed. Please try again."
                )
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        PhotoPostSerializer(post).data,
        status=status.HTTP_201_CREATED,
    )



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def photo_posts_feed(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before viewing posts."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get all profile IDs belonging to the current tenant.
    tenant_profile_ids = list(
        Profile.objects.filter(
            tenant=tenant
        ).values_list("id", flat=True)
    )

    # Get accepted matches without tenant JOINs.
    accepted_matches = Match.objects.filter(
        Q(sender_id=profile.id) | Q(receiver_id=profile.id),
        status="accepted",
        sender_id__in=tenant_profile_ids,
        receiver_id__in=tenant_profile_ids,
    ).values_list(
        "sender_id",
        "receiver_id",
    )

    # Always include the current user's own profile.
    allowed_profile_ids = {profile.id}

    # Include profiles with accepted matches only.
    for sender_id, receiver_id in accepted_matches:
        allowed_profile_ids.add(sender_id)
        allowed_profile_ids.add(receiver_id)

    # Fetch posts only from allowed profiles in this tenant.
    posts = PhotoPost.objects.filter(
        profile_id__in=allowed_profile_ids,
        profile__tenant=tenant,
    ).select_related(
        "profile"
    ).order_by("-created_at")

    serializer = PhotoPostSerializer(
        posts,
        many=True,
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_photo_post(request, post_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "No tenant is associated with this user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Your profile was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        post = PhotoPost.objects.get(
            id=post_id,
            profile=profile,
            profile__tenant=tenant,
        )
    except PhotoPost.DoesNotExist:
        return Response(
            {
                "error": (
                    "Post not found or you cannot delete this post."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if post.image_public_id:
        try:
            result = cloudinary.uploader.destroy(
                post.image_public_id,
                resource_type="image",
            )

            if result.get("result") not in ("ok", "not found"):
                return Response(
                    {
                        "error": (
                            "Could not delete the image from storage."
                        )
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        except Exception as e:
            print("Cloudinary post delete error:", repr(e))
            return Response(
                {
                    "error": (
                        "Post deletion failed. Please try again."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

    post.delete()

    return Response(
        {"message": "Photo post deleted successfully."},
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def subscription_plans(request):
    user_profile = getattr(
        request.user,
        "user_profile",
        None,
    )
    user_role = getattr(user_profile, "role", None)

    if request.method == "GET":
        plans = SubscriptionPlan.objects.all()

        # Non-admin users can see active plans only.
        if user_role != "super_admin":
            plans = plans.filter(is_active=True)

        serializer = SubscriptionPlanSerializer(
            plans.order_by("price"),
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    # Only Super Admin can create subscription plans.
    if user_role != "super_admin":
        return Response(
            {
                "error": (
                    "Only Super Admin can create subscription plans."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = SubscriptionPlanSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


# Chat: Get conversation messages and send a message
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_messages(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {
                "error": (
                    "Super Admin cannot access end-user chats."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Get the logged-in user's profile.
    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {
                "error": (
                    "Create your profile before using chat."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get the other user's profile.
    try:
        other_profile = Profile.objects.get(
            id=profile_id,
            tenant=tenant,
        )
    except (Profile.DoesNotExist, ValueError, TypeError):
        return Response(
            {
                "error": (
                    "Chat profile not found in your tenant."
                )
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # A user cannot start a chat with their own profile.
    if current_profile.id == other_profile.id:
        return Response(
            {
                "error": (
                    "You cannot start a chat with your own profile."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify that both profiles have an accepted match.
    accepted_match = Match.objects.filter(
        Q(
            sender=current_profile,
            receiver=other_profile,
        )
        |
        Q(
            sender=other_profile,
            receiver=current_profile,
        ),
        status="accepted",
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).exists()

    if not accepted_match:
        return Response(
            {
                "error": (
                    "You can chat only with accepted matches."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # GET: Fetch the conversation between both profiles.
    if request.method == "GET":

        # Mark incoming messages as read.
        Message.objects.filter(
            sender=other_profile,
            receiver=current_profile,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

        messages = Message.objects.filter(
            Q(
                sender=current_profile,
                receiver=other_profile,
            )
            |
            Q(
                sender=other_profile,
                receiver=current_profile,
            )
        ).select_related(
            "sender",
            "receiver",
        ).order_by("created_at")

        serializer = MessageSerializer(
            messages,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    # POST: Send a new message.
    content = request.data.get("content", "")

    if not isinstance(content, str):
        return Response(
            {
                "error": (
                    "Message content must be text."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    content = content.strip()

    if not content:
        return Response(
            {
                "error": (
                    "Message cannot be empty."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(content) > 2000:
        return Response(
            {
                "error": (
                    "Message cannot exceed 2000 characters."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    message = Message.objects.create(
        sender=current_profile,
        receiver=other_profile,
        content=content,
    )

    serializer = MessageSerializer(message)

    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED,
    )