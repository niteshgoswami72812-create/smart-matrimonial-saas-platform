from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("super_admin", "Super Admin"),
        ("host", "Host"),
        ("end_user", "End User"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="user_profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="end_user",
    )

    tenant = models.ForeignKey(
        "Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Tenant(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("premium", "Premium"),
    ]

    name = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        unique=True,
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    duration_days = models.PositiveIntegerField(default=30)
    max_profiles = models.PositiveIntegerField(default=25)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ₹{self.price}"


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("pending", "Pending"),
    ]

    # Individual account that owns this subscription.
    # Nullable temporarily to preserve existing subscription records.
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscriptions",
    )

    # Retained for existing tenant structure and compatibility.
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subscriptions",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        owner = self.user.username if self.user else (
            self.tenant.name if self.tenant else "Unknown User"
        )
        return f"{owner} - {self.plan.name}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="subscription_payments",
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True,
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="INR",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
    )

    failure_reason = models.TextField(blank=True)

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # PDF receipt storage
    receipt_pdf = models.FileField(
        upload_to="payment_receipts/",
        null=True,
        blank=True,
    )

    # Email delivery tracking
    receipt_email_sent = models.BooleanField(default=False)

    receipt_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    receipt_email_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        owner = self.created_by.username
        return f"{owner} - ₹{self.amount} - {self.status}"

class TermsAcceptance(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="terms_acceptances",
    )
    terms_version = models.CharField(
        max_length=20,
        default="1.0",
    )
    privacy_version = models.CharField(
        max_length=20,
        default="1.0",
    )
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"{self.user.username} - Terms v{self.terms_version}"