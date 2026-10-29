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

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
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
        return f"{self.tenant.name} - {self.plan.name}"