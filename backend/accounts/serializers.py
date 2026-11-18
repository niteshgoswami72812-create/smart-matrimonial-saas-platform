from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Tenant, UserProfile, TermsAcceptance


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    tenant_slug = serializers.SlugField()

    accept_terms = serializers.BooleanField(
        required=True,
        write_only=True,
    )
    accept_privacy = serializers.BooleanField(
        required=True,
        write_only=True,
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_tenant_slug(self, value):
        try:
            return Tenant.objects.get(
                slug=value,
                is_active=True,
            )
        except Tenant.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid or inactive matrimony tenant."
            )

    def validate(self, attrs):
        if not attrs.get("accept_terms"):
            raise serializers.ValidationError({
                "accept_terms": "You must accept Terms & Conditions."
            })

        if not attrs.get("accept_privacy"):
            raise serializers.ValidationError({
                "accept_privacy": "You must acknowledge the Privacy Policy."
            })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tenant = validated_data.pop("tenant_slug")

        validated_data.pop("accept_terms")
        validated_data.pop("accept_privacy")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        UserProfile.objects.create(
            user=user,
            role="end_user",
            tenant=tenant,
        )

        TermsAcceptance.objects.create(
            user=user,
            terms_version="1.0",
            privacy_version="1.0",
        )

        return user