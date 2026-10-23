from rest_framework import serializers
from .models import Profile, Preferences, Match

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
                "max_age": "Maximum age must be greater than or equal to minimum age."
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