from rest_framework import serializers
from .models import (
    Profile,
    Preferences,
    Match,
    AIMatchExplanation,
    ProfilePhoto,
    PhotoPost,
    Message,
)
from accounts.models import SubscriptionPlan, Subscription


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        exclude = ["user", "tenant"]


class PreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preferences
        exclude = ["user", "tenant"]

    def validate(self, attrs):
        min_age = attrs.get(
            "min_age",
            getattr(self.instance, "min_age", 21),
        )
        max_age = attrs.get(
            "max_age",
            getattr(self.instance, "max_age", 30),
        )

        if min_age > max_age:
            raise serializers.ValidationError({
                "max_age": (
                    "Maximum age must be greater than or equal "
                    "to minimum age."
                )
            })

        return attrs


class MatchSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source="sender.full_name",
        read_only=True,
    )
    receiver_name = serializers.CharField(
        source="receiver.full_name",
        read_only=True,
    )

    class Meta:
        model = Match
        fields = [
            "id",
            "sender",
            "sender_name",
            "receiver",
            "receiver_name",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sender",
            "status",
            "created_at",
            "updated_at",
        ]


class AIMatchExplanationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMatchExplanation
        fields = [
            "id",
            "compatibility",
            "summary",
            "reasons",
            "generated_at",
        ]
        read_only_fields = fields


class ProfilePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfilePhoto
        fields = [
            "id",
            "image_url",
            "is_primary",
            "uploaded_at",
        ]
        read_only_fields = [
            "id",
            "image_url",
            "uploaded_at",
        ]


class PhotoPostSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(
        source="profile.id",
        read_only=True,
    )
    profile_name = serializers.CharField(
        source="profile.full_name",
        read_only=True,
    )

    class Meta:
        model = PhotoPost
        fields = [
            "id",
            "profile_id",
            "profile_name",
            "image_url",
            "caption",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(
        source="sender.full_name",
        read_only=True,
    )
    receiver_name = serializers.CharField(
        source="receiver.full_name",
        read_only=True,
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "sender_name",
            "receiver",
            "receiver_name",
            "content",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "sender",
            "sender_name",
            "receiver",
            "receiver_name",
            "is_read",
            "read_at",
            "created_at",
        ]

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(
        source="plan.name",
        read_only=True,
    )
    tenant_name = serializers.CharField(
        source="tenant.name",
        read_only=True,
    )

    class Meta:
        model = Subscription
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "plan",
            "plan_name",
            "status",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
        ]