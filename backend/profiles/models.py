from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Profile(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="matrimonial_profile",
    )
    tenant = models.ForeignKey(
        "accounts.Tenant",
        on_delete=models.PROTECT,
        related_name="profiles",

    )
    full_name = models.CharField(max_length=150)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
    )

    city = models.CharField(max_length=100, blank=True)
    education = models.CharField(max_length=150, blank=True)
    profession = models.CharField(max_length=150, blank=True)
    about_me = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def clean(self):
        super().clean()

        if self.date_of_birth and self.date_of_birth > timezone.localdate():
            raise ValidationError({
                "date_of_birth": "Date of birth cannot be in the future."
            })
    def __str__(self):
        return self.full_name


class Preferences(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="partner_preferences",
    )

    tenant = models.ForeignKey(
        "accounts.Tenant",
        on_delete=models.PROTECT,
        related_name="preferences",

    )

    min_age = models.PositiveSmallIntegerField(default=21)
    max_age = models.PositiveSmallIntegerField(default=30)
    preferred_city = models.CharField(max_length=100, blank=True)
    preferred_education = models.CharField(max_length=150, blank=True)
    preferred_profession = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if self.min_age > self.max_age:
            raise ValidationError({
                "max_age": "Maximum age must be greater than or equal to minimum age."
            })

    def __str__(self):
        return f"Preferences for {self.user.username}"


class ProfilePhoto(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    image_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile"],
                condition=models.Q(is_primary=True),
                name="unique_primary_photo_per_profile",
            ),
        ]
    def __str__(self):
        return f"Photo for {self.profile.full_name}"

class Match(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    sender = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="sent_matches",
    )
    receiver = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="received_matches",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "receiver"],
                name="unique_sender_receiver_match",
            ),
        ]

    def clean(self):
        super().clean()

        if self.sender_id and self.receiver_id:
            if self.sender_id == self.receiver_id:
                raise ValidationError(
                    "You cannot send a match request to your own profile."
                )

    def __str__(self):
        return f"{self.sender.full_name} -> {self.receiver.full_name}"


class CompatibilityScore(models.Model):
    profile_one = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="compatibility_scores_as_one",
    )
    profile_two = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="compatibility_scores_as_two",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile_one", "profile_two"],
                name="unique_profile_pair_compatibility",
            ),
        ]

    def __str__(self):
        return (
            f"{self.profile_one.full_name} - "
            f"{self.profile_two.full_name}: {self.score}%"
        )