
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


# =========================================================
# PROFILE
# =========================================================

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

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    education = models.CharField(
        max_length=150,
        blank=True,
    )

    profession = models.CharField(
        max_length=150,
        blank=True,
    )

    about_me = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    # Last time the user was active.
    # Online status will be managed through WebSockets.
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    def clean(self):
        super().clean()

        if (
            self.date_of_birth
            and self.date_of_birth > timezone.localdate()
        ):
            raise ValidationError({
                "date_of_birth": (
                    "Date of birth cannot be in the future."
                )
            })

    def __str__(self):
        return self.full_name


# =========================================================
# PREFERENCES
# =========================================================

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

    preferred_city = models.CharField(
        max_length=100,
        blank=True,
    )

    preferred_education = models.CharField(
        max_length=150,
        blank=True,
    )

    preferred_profession = models.CharField(
        max_length=150,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if self.min_age > self.max_age:
            raise ValidationError({
                "max_age": (
                    "Maximum age must be greater than "
                    "or equal to minimum age."
                )
            })

    def __str__(self):
        return f"Preferences for {self.user.username}"


# =========================================================
# PROFILE PHOTOS
# =========================================================


class ProfilePhoto(models.Model):

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    image_url = models.URLField(max_length=500)

    image_public_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    is_primary = models.BooleanField(default=False)

    # TiDB-compatible conditional uniqueness
    primary_profile_id = models.GeneratedField(
        expression=models.Case(
            models.When(
                is_primary=True,
                then=models.F("profile_id"),
            ),
            default=models.Value(
                None,
                output_field=models.BigIntegerField(),
            ),
            output_field=models.BigIntegerField(),
        ),
        output_field=models.BigIntegerField(),
        db_persist=False,
        null=True,
        editable=False,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["primary_profile_id"],
                name="unique_primary_photo_per_profile",
            ),
        ]

    def __str__(self):
        return f"Photo for {self.profile.full_name}"

# =========================================================
# PHOTO POSTS
# =========================================================

class PhotoPost(models.Model):

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="photo_posts",
    )

    image_url = models.URLField(max_length=500)

    image_public_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    caption = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Post by {self.profile.full_name}"


# =========================================================
# MATCH SYSTEM
# =========================================================

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
                    "You cannot send a match request "
                    "to your own profile."
                )

    def __str__(self):
        return (
            f"{self.sender.full_name} -> "
            f"{self.receiver.full_name}"
        )


# =========================================================
# COMPATIBILITY SCORE
# =========================================================

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

    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )

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


# =========================================================
# AI MATCH EXPLANATION
# =========================================================

class AIMatchExplanation(models.Model):

    compatibility = models.OneToOneField(
        CompatibilityScore,
        on_delete=models.CASCADE,
        related_name="ai_explanation",
    )

    summary = models.TextField()

    reasons = models.JSONField(default=list)

    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"AI Explanation: "
            f"{self.compatibility.profile_one.full_name} - "
            f"{self.compatibility.profile_two.full_name}"
        )


# =========================================================
# CHAT MESSAGES
# =========================================================

class Message(models.Model):

    sender = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )

    receiver = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )

    content = models.TextField(max_length=2000)

    is_read = models.BooleanField(default=False)

    # Exact time when the receiver read the message.
    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.sender.full_name} -> "
            f"{self.receiver.full_name}"
        )


# =========================================================
# PROFILE BLOCK
# =========================================================

class ProfileBlock(models.Model):

    blocker = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="blocks_created",
    )

    blocked = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )

    tenant = models.ForeignKey(
        "accounts.Tenant",
        on_delete=models.PROTECT,
        related_name="profile_blocks",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"],
                name="unique_profile_block",
            ),
        ]

    def clean(self):
        super().clean()

        if self.blocker_id and self.blocked_id:

            if self.blocker_id == self.blocked_id:
                raise ValidationError(
                    "You cannot block your own profile."
                )

            if self.blocker.tenant_id != self.blocked.tenant_id:
                raise ValidationError(
                    "Both profiles must belong to the same tenant."
                )

            if self.tenant_id != self.blocker.tenant_id:
                raise ValidationError(
                    "Block record tenant does not match the profiles."
                )

    def __str__(self):
        return (
            f"{self.blocker.full_name} blocked "
            f"{self.blocked.full_name}"
        )


# =========================================================
# REMOVED CONNECTIONS
# =========================================================

class RemovedProfile(models.Model):

    owner = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="removed_profiles",
    )

    removed_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="removed_by_users",
    )

    tenant = models.ForeignKey(
        "accounts.Tenant",
        on_delete=models.PROTECT,
        related_name="removed_profiles",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "removed_profile"],
                name="unique_removed_profile",
            ),
        ]

    def clean(self):
        super().clean()

        if self.owner_id and self.removed_profile_id:

            if self.owner_id == self.removed_profile_id:
                raise ValidationError(
                    "You cannot remove your own profile."
                )

            if (
                self.owner.tenant_id
                != self.removed_profile.tenant_id
            ):
                raise ValidationError(
                    "Both profiles must belong to the same tenant."
                )

            if self.tenant_id != self.owner.tenant_id:
                raise ValidationError(
                    "Removal record tenant does not match the profiles."
                )

    def __str__(self):
        return (
            f"{self.owner.full_name} removed "
            f"{self.removed_profile.full_name}"
        )
