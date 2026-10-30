from django.db import IntegrityError
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.tenant_utils import get_user_tenant
from .models import (
    Profile,
    Preferences,
    Match,
    CompatibilityScore,
    AIMatchExplanation,
)
from .serializers import (
    ProfileSerializer,
    PreferencesSerializer,
    MatchSerializer,
    AIMatchExplanationSerializer,
)
from datetime import date
from decimal import Decimal

def calculate_compatibility_score(profile, preferences):
    """Calculate compatibility score out of 100 using saved preferences."""
    today = date.today()
    criteria = []

    # 1. Age preference — 40%
    if profile.date_of_birth:
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
        criteria.append((
            40,
            preferences.min_age <= age <= preferences.max_age,
        ))

    # 2. City preference — 25%
    if preferences.preferred_city.strip():
        criteria.append((
            25,
            profile.city.strip().casefold()
            == preferences.preferred_city.strip().casefold(),
        ))

    # 3. Education preference — 20%
    if preferences.preferred_education.strip():
        criteria.append((
            20,
            profile.education.strip().casefold()
            == preferences.preferred_education.strip().casefold(),
        ))

    # 4. Profession preference — 15%
    if preferences.preferred_profession.strip():
        criteria.append((
            15,
            profile.profession.strip().casefold()
            == preferences.preferred_profession.strip().casefold(),
        ))

    if not criteria:
        return 0.00

    available_weight = sum(weight for weight, _ in criteria)
    matched_weight = sum(
        weight for weight, matched in criteria if matched
    )

    return round((matched_weight / available_weight) * 100, 2)

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
                < (profile.date_of_birth.month, profile.date_of_birth.day)
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
            {"error": "Super Admin cannot generate match explanations here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile before generating an explanation."},
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
            {"error": "You cannot explain compatibility with your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        preferences = Preferences.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Preferences.DoesNotExist:
        return Response(
            {"error": "Create your preferences before generating an explanation."},
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
        profiles = Profile.objects.filter(tenant=tenant)

    serializer = ProfileSerializer(profiles, many=True)
    return Response(serializer.data)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def calculate_profile_compatibility(request, profile_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot calculate end-user compatibility here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        current_profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile before calculating compatibility."},
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
            {"error": "You cannot calculate compatibility with your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        preferences = Preferences.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Preferences.DoesNotExist:
        return Response(
            {"error": "Create your preferences before calculating compatibility."},
            status=status.HTTP_404_NOT_FOUND,
        )

    score = calculate_compatibility_score(target_profile, preferences)

    compatibility, _ = CompatibilityScore.objects.update_or_create(
        profile_one=current_profile,
        profile_two=target_profile,
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
            {"error": "Super Admin does not have an end-user profile here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Profile not found. Please create your profile first."},
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
        return Response(serializer.data, status=status.HTTP_200_OK)

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
            {"error": "Super Admin does not have end-user preferences here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        preferences = Preferences.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Preferences.DoesNotExist:
        return Response(
            {"error": "Preferences not found. Please create preferences first."},
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
        return Response(serializer.data, status=status.HTTP_200_OK)

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
            {"error": "Create your profile before sending a match request."},
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

    if sender.pk == receiver.pk:
        return Response(
            {"error": "You cannot send a match request to your own profile."},
            status=status.HTTP_400_BAD_REQUEST,
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
            {"error": "You have already sent a request to this profile."},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        MatchSerializer(match).data,
        status=status.HTTP_201_CREATED,
    )


# Task 16: List sent and received match requests
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_matches(request):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot access end-user match requests here."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        profile = Profile.objects.get(
            user=request.user,
            tenant=tenant,
        )
    except Profile.DoesNotExist:
        return Response(
            {"error": "Create your profile before viewing match requests."},
            status=status.HTTP_404_NOT_FOUND,
        )
    matches = Match.objects.filter(
        sender__tenant=tenant,
        receiver__tenant=tenant,
    ).filter(
        Q(sender=profile) | Q(receiver=profile)
    ).select_related(
        "sender", "receiver"
    ).order_by("-created_at")

    return Response(MatchSerializer(matches, many=True).data)


# Task 16: Accept or reject a received match request
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_match_status(request, match_id):
    tenant = get_user_tenant(request.user)

    if tenant is None:
        return Response(
            {"error": "Super Admin cannot update end-user match requests."},
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
            {"error": "Status must be either 'accepted' or 'rejected'."},
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
            {"error": "Only pending match requests can be updated."},
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
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )
