
from decimal import Decimal
from uuid import uuid4
from datetime import timedelta
from io import BytesIO
from html import escape

import razorpay

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.http import FileResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .permissions import IsSuperAdmin, IsHost, IsEndUser
from .models import Payment, Subscription, SubscriptionPlan
from .serializers import SignupSerializer
from .tenant_utils import get_user_tenant


# =========================================================
# DASHBOARDS
# =========================================================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def super_admin_dashboard(request):
    return Response({
        "message": "Super Admin access granted",
        "role": request.user.user_profile.role,
    })


@api_view(["GET"])
@permission_classes([IsHost])
def host_dashboard(request):
    return Response({
        "message": "Host access granted",
        "role": request.user.user_profile.role,
    })


@api_view(["GET"])
@permission_classes([IsEndUser])
def end_user_dashboard(request):
    return Response({
        "message": "End User access granted",
        "role": request.user.user_profile.role,
    })


# =========================================================
# SUBSCRIPTION APIs
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):

    subscription = (
        Subscription.objects
        .filter(user=request.user)
        .select_related("plan", "tenant")
        .order_by("-created_at")
        .first()
    )

    if not subscription:
        return Response(
            {"error": "No subscription found for this account."},
            status=404,
        )

    return Response({
        "id": subscription.id,
        "user": request.user.username,
        "tenant": (
            subscription.tenant.name
            if subscription.tenant else None
        ),
        "plan": subscription.plan.name,
        "price": str(subscription.plan.price),
        "status": subscription.status,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "max_profiles": subscription.plan.max_profiles,
    })


@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def all_subscriptions(request):

    subscriptions = (
        Subscription.objects
        .select_related("tenant", "plan", "user")
        .order_by("-created_at")
    )

    data = [
        {
            "id": subscription.id,
            "user": (
                subscription.user.username
                if subscription.user else None
            ),
            "tenant": (
                subscription.tenant.name
                if subscription.tenant else None
            ),
            "plan": subscription.plan.name,
            "price": str(subscription.plan.price),
            "status": subscription.status,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "max_profiles": subscription.plan.max_profiles,
        }
        for subscription in subscriptions
    ]

    return Response(data)


@api_view(["PATCH"])
@permission_classes([IsSuperAdmin])
def update_subscription_status(request, subscription_id):

    allowed_statuses = [
        "pending",
        "active",
        "expired",
        "cancelled",
    ]

    new_status = request.data.get("status")

    if new_status not in allowed_statuses:
        return Response(
            {
                "error": "Invalid status.",
                "allowed_statuses": allowed_statuses,
            },
            status=400,
        )

    try:
        subscription = (
            Subscription.objects
            .select_related("tenant", "plan", "user")
            .get(id=subscription_id)
        )

    except Subscription.DoesNotExist:
        return Response(
            {"error": "Subscription not found."},
            status=404,
        )

    subscription.status = new_status

    subscription.save(update_fields=[
        "status",
        "updated_at",
    ])

    return Response({
        "message": "Subscription status updated successfully.",
        "id": subscription.id,
        "user": (
            subscription.user.username
            if subscription.user else None
        ),
        "tenant": (
            subscription.tenant.name
            if subscription.tenant else None
        ),
        "plan": subscription.plan.name,
        "status": subscription.status,
    })


# =========================================================
# SIGNUP
# =========================================================

@api_view(["POST"])
@permission_classes([])
def signup(request):

    serializer = SignupSerializer(data=request.data)

    if serializer.is_valid():

        user = serializer.save()

        return Response(
            {
                "message": "Account created successfully. Please log in.",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.user_profile.role,
                },
            },
            status=201,
        )

    return Response(
        serializer.errors,
        status=400,
    )


# =========================================================
# PDF RECEIPT GENERATION
# =========================================================

def generate_payment_receipt_pdf(payment):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=22,
        textColor=colors.HexColor("#9D174D"),
        spaceAfter=12,
    )

    story = []

    customer = payment.created_by

    customer_name = (
        customer.get_full_name().strip()
        or customer.username
    )

    payment_date = timezone.localtime(
        payment.verified_at or payment.created_at
    ).strftime("%d %B %Y, %I:%M %p")

    story.append(
        Paragraph("PAYMENT RECEIPT", title_style)
    )

    story.append(
        Paragraph(
            "Smart Matrimonial SaaS Platform",
            styles["Heading2"],
        )
    )

    story.append(Spacer(1, 10 * mm))

    receipt_data = [
        ("Receipt Number", f"PAY-{payment.id:06d}"),
        ("Customer Name", customer_name),
        ("Email Address", customer.email or "Not available"),
        ("Subscription Plan", payment.plan.name),
        (
            "Amount Paid",
            f"{payment.currency} {payment.amount}",
        ),
        ("Payment Status", payment.status.upper()),
        ("Razorpay Order ID", payment.razorpay_order_id),
        (
            "Razorpay Payment ID",
            payment.razorpay_payment_id or "Not available",
        ),
        ("Payment Date", payment_date),
    ]

    if payment.subscription:

        receipt_data.extend([
            (
                "Subscription Status",
                payment.subscription.status.upper(),
            ),
            (
                "Subscription Start",
                str(payment.subscription.start_date),
            ),
            (
                "Subscription End",
                str(payment.subscription.end_date),
            ),
        ])

    table_data = []

    for label, value in receipt_data:

        table_data.append([
            Paragraph(
                f"<b>{escape(str(label))}</b>",
                styles["BodyText"],
            ),
            Paragraph(
                escape(str(value)),
                styles["BodyText"],
            ),
        ])

    receipt_table = Table(
        table_data,
        colWidths=[55 * mm, 115 * mm],
    )

    receipt_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#FCE7F3"),
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (0, -1),
                colors.HexColor("#831843"),
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.lightgrey,
            ),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ])
    )

    story.append(receipt_table)

    story.append(Spacer(1, 15 * mm))

    story.append(
        Paragraph(
            "Thank you for choosing Smart Matrimonial SaaS.",
            styles["BodyText"],
        )
    )

    story.append(
        Paragraph(
            "This is a computer-generated payment receipt.",
            styles["Italic"],
        )
    )

    document.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


# =========================================================
# GENERATE, SAVE AND EMAIL RECEIPT
# =========================================================

def create_and_email_payment_receipt(payment):

    # Generate and save PDF if it does not exist.
    try:

        if not payment.receipt_pdf:

            pdf_bytes = generate_payment_receipt_pdf(payment)

            payment.receipt_pdf.save(
                f"receipt_{payment.id}.pdf",
                ContentFile(pdf_bytes),
                save=False,
            )

            payment.save(update_fields=[
                "receipt_pdf",
                "updated_at",
            ])

        else:

            with payment.receipt_pdf.open("rb") as pdf_file:
                pdf_bytes = pdf_file.read()

    except Exception as exc:

        payment.receipt_email_error = (
            f"Receipt PDF generation/storage failed: {str(exc)}"
        )

        payment.save(update_fields=[
            "receipt_email_error",
            "updated_at",
        ])

        return {
            "pdf_available": False,
            "email_sent": False,
        }

    # Do not send the same receipt email again.
    if payment.receipt_email_sent:

        return {
            "pdf_available": True,
            "email_sent": True,
        }

    try:

        recipient_email = payment.created_by.email

        if not recipient_email:
            raise ValueError(
                "Registered email address is missing."
            )

        customer_name = (
            payment.created_by.get_full_name().strip()
            or payment.created_by.username
        )

        email = EmailMessage(
            subject=(
                f"Payment Receipt - Smart Matrimonial SaaS "
                f"PAY-{payment.id:06d}"
            ),

            body=(
                f"Hello {customer_name},\n\n"
                "Your subscription payment was successful.\n\n"
                f"Plan: {payment.plan.name}\n"
                f"Amount: {payment.currency} {payment.amount}\n"
                f"Payment ID: {payment.razorpay_payment_id}\n\n"
                "Your payment receipt is attached as a PDF.\n\n"
                "Thank you for choosing Smart Matrimonial SaaS."
            ),

            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )

        email.attach(
            f"Payment_Receipt_{payment.id}.pdf",
            pdf_bytes,
            "application/pdf",
        )

        sent_count = email.send(fail_silently=False)

        if sent_count != 1:
            raise RuntimeError(
                "Receipt email was not accepted."
            )

        payment.receipt_email_sent = True
        payment.receipt_email_sent_at = timezone.now()
        payment.receipt_email_error = ""

        payment.save(update_fields=[
            "receipt_email_sent",
            "receipt_email_sent_at",
            "receipt_email_error",
            "updated_at",
        ])

        return {
            "pdf_available": True,
            "email_sent": True,
        }

    except Exception as exc:

        payment.receipt_email_sent = False
        payment.receipt_email_error = str(exc)[:4000]

        payment.save(update_fields=[
            "receipt_email_sent",
            "receipt_email_error",
            "updated_at",
        ])

        return {
            "pdf_available": True,
            "email_sent": False,
        }


# =========================================================
# CREATE RAZORPAY SUBSCRIPTION ORDER
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_subscription_order(request):

    try:
        role = request.user.user_profile.role

    except Exception:
        return Response(
            {"error": "User profile not found."},
            status=403,
        )

    if role not in ["host", "end_user"]:
        return Response(
            {"error": "You are not allowed to purchase subscriptions."},
            status=403,
        )

    tenant = get_user_tenant(request.user)

    plan_id = request.data.get("plan_id")

    try:
        plan_id = int(plan_id)

    except (TypeError, ValueError):
        return Response(
            {"error": "A valid plan_id is required."},
            status=400,
        )

    plan = SubscriptionPlan.objects.filter(
        id=plan_id,
        is_active=True,
    ).first()

    if not plan:
        return Response(
            {"error": "Subscription plan not found or inactive."},
            status=404,
        )

    if plan.price <= Decimal("0.00"):
        return Response(
            {"error": "Free plans do not require online payment."},
            status=400,
        )

    amount_paise = int(plan.price * Decimal("100"))

    if amount_paise <= 0:
        return Response(
            {"error": "Invalid subscription amount."},
            status=400,
        )

    try:

        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        order = client.order.create(
            data={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"sub_{uuid4().hex[:30]}",
                "notes": {
                    "buyer_user_id": str(request.user.id),
                    "tenant_id": str(tenant.id) if tenant else "",
                    "plan_id": str(plan.id),
                },
            }
        )

    except Exception:

        return Response(
            {
                "error": "Unable to create Razorpay order. Please try again."
            },
            status=502,
        )

    razorpay_order_id = order.get("id")

    if not razorpay_order_id:
        return Response(
            {"error": "Razorpay did not return a valid order ID."},
            status=502,
        )

    payment = Payment.objects.create(
        tenant=tenant,
        plan=plan,
        created_by=request.user,
        razorpay_order_id=razorpay_order_id,
        amount=plan.price,
        currency="INR",
        status="created",
    )

    return Response(
        {
            "message": "Razorpay order created successfully.",
            "payment_record_id": payment.id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "tenant": tenant.name if tenant else None,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "price": str(plan.price),
            },
        },
        status=201,
    )


# =========================================================
# VERIFY RAZORPAY PAYMENT AND ACTIVATE SUBSCRIPTION
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_subscription_payment(request):

    try:
        role = request.user.user_profile.role

    except Exception:
        return Response(
            {"error": "User profile not found."},
            status=403,
        )

    if role not in ["host", "end_user"]:
        return Response(
            {
                "error": "You are not allowed to verify subscription payments."
            },
            status=403,
        )

    order_id = request.data.get("razorpay_order_id")
    payment_id = request.data.get("razorpay_payment_id")
    signature = request.data.get("razorpay_signature")

    if not all([order_id, payment_id, signature]):
        return Response(
            {
                "error": "Order ID, Payment ID and Signature are required."
            },
            status=400,
        )

    payment = (
        Payment.objects
        .select_related(
            "plan",
            "tenant",
            "subscription",
            "created_by",
        )
        .filter(
            created_by=request.user,
            razorpay_order_id=order_id,
        )
        .first()
    )

    if not payment:
        return Response(
            {"error": "Payment record not found."},
            status=404,
        )

    # Verify Razorpay signature.
    try:

        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })

    except razorpay.errors.SignatureVerificationError:

        return Response(
            {"error": "Invalid payment signature."},
            status=400,
        )

    except Exception:

        return Response(
            {"error": "Unable to verify payment signature."},
            status=502,
        )

    # Fetch payment from Razorpay.
    try:
        razorpay_payment = client.payment.fetch(payment_id)

    except Exception:
        return Response(
            {"error": "Unable to verify payment with Razorpay."},
            status=502,
        )

    expected_amount = int(
        payment.amount * Decimal("100")
    )

    try:
        received_amount = int(
            razorpay_payment.get("amount", -1)
        )

    except (TypeError, ValueError):
        received_amount = -1

    if razorpay_payment.get("order_id") != order_id:
        return Response(
            {"error": "Payment does not belong to this order."},
            status=400,
        )

    if received_amount != expected_amount:
        return Response(
            {
                "error": "Payment amount does not match the subscription plan."
            },
            status=400,
        )

    if razorpay_payment.get("currency") != payment.currency:
        return Response(
            {"error": "Payment currency mismatch."},
            status=400,
        )

    if razorpay_payment.get("status") != "captured":
        return Response(
            {
                "error": "Payment is not captured yet. Please try again."
            },
            status=409,
        )

    already_verified = False

    # Activate subscription inside database transaction.
    with transaction.atomic():

        locked_payment = (
            Payment.objects
            .select_for_update()
            .select_related(
                "plan",
                "tenant",
                "subscription",
                "created_by",
            )
            .get(
                id=payment.id,
                created_by=request.user,
            )
        )

        # Duplicate verification protection.
        if locked_payment.status == "paid":

            if (
                locked_payment.razorpay_payment_id == payment_id
                and locked_payment.subscription_id
            ):
                subscription = locked_payment.subscription
                already_verified = True

            else:
                return Response(
                    {"error": "This order has already been paid."},
                    status=409,
                )

        else:

            if locked_payment.status != "created":
                return Response(
                    {
                        "error": "This payment cannot be verified again."
                    },
                    status=409,
                )

            if Payment.objects.filter(
                razorpay_payment_id=payment_id
            ).exclude(id=locked_payment.id).exists():

                return Response(
                    {
                        "error": "This Razorpay payment ID is already used."
                    },
                    status=409,
                )

            # Expire only this user's previous active subscriptions.
            Subscription.objects.filter(
                user=request.user,
                status="active",
            ).update(
                status="expired",
                updated_at=timezone.now(),
            )

            start_date = timezone.localdate()

            end_date = start_date + timedelta(
                days=locked_payment.plan.duration_days
            )

            subscription = Subscription.objects.create(
                user=request.user,
                tenant=locked_payment.tenant,
                plan=locked_payment.plan,
                status="active",
                start_date=start_date,
                end_date=end_date,
            )

            locked_payment.razorpay_payment_id = payment_id
            locked_payment.status = "paid"
            locked_payment.subscription = subscription
            locked_payment.verified_at = timezone.now()

            locked_payment.save(update_fields=[
                "razorpay_payment_id",
                "status",
                "subscription",
                "verified_at",
                "updated_at",
            ])

    # Generate PDF and send email AFTER transaction commit.
    receipt_result = create_and_email_payment_receipt(
        locked_payment
    )

    locked_payment.refresh_from_db()

    return Response({
        "message": (
            "Payment already verified successfully."
            if already_verified
            else "Payment verified and subscription activated successfully."
        ),

        "payment_status": "paid",

        "payment_record_id": locked_payment.id,

        "receipt": {
            "available": receipt_result["pdf_available"],
            "email_sent": receipt_result["email_sent"],
            "receipt_id": locked_payment.id,
        },

        "subscription": {
            "id": subscription.id,
            "user": request.user.username,
            "tenant": (
                subscription.tenant.name
                if subscription.tenant else None
            ),
            "plan": subscription.plan.name,
            "status": subscription.status,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "max_profiles": subscription.plan.max_profiles,
        },

    }, status=200)


# =========================================================
# USER'S PAYMENT RECEIPT LIST
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payment_receipts(request):

    payments = (
        Payment.objects
        .filter(
            created_by=request.user,
            status="paid",
        )
        .select_related("plan", "subscription")
        .order_by("-verified_at", "-created_at")
    )

    data = []

    for payment in payments:

        data.append({
            "id": payment.id,
            "receipt_number": f"PAY-{payment.id:06d}",
            "plan": payment.plan.name,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "payment_status": payment.status,
            "razorpay_order_id": payment.razorpay_order_id,
            "razorpay_payment_id": payment.razorpay_payment_id,
            "payment_date": payment.verified_at,
            "receipt_available": bool(payment.receipt_pdf),
            "email_sent": payment.receipt_email_sent,
            "download_url": (
                f"/api/accounts/payment-receipts/{payment.id}/download/"
                if payment.receipt_pdf else None
            ),
        })

    return Response(data)


# =========================================================
# SECURE PDF RECEIPT DOWNLOAD
# =========================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_payment_receipt(request, payment_id):

    payment = (
        Payment.objects
        .filter(
            id=payment_id,
            created_by=request.user,
            status="paid",
        )
        .first()
    )

    if not payment:
        return Response(
            {"error": "Payment receipt not found."},
            status=404,
        )

    if not payment.receipt_pdf:
        return Response(
            {"error": "PDF receipt is not available yet."},
            status=404,
        )

    try:
        pdf_file = payment.receipt_pdf.open("rb")

        return FileResponse(
            pdf_file,
            as_attachment=True,
            filename=f"Payment_Receipt_{payment.id}.pdf",
            content_type="application/pdf",
        )

    except (OSError, ValueError):
        return Response(
            {"error": "Unable to open PDF receipt."},
            status=404,
        )


# =========================================================
# RETRY RECEIPT EMAIL
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_payment_receipt_email(request, payment_id):

    payment = (
        Payment.objects
        .select_related(
            "plan",
            "subscription",
            "created_by",
        )
        .filter(
            id=payment_id,
            created_by=request.user,
            status="paid",
        )
        .first()
    )

    if not payment:
        return Response(
            {"error": "Payment receipt not found."},
            status=404,
        )

    if payment.receipt_email_sent:
        return Response(
            {"message": "Receipt email has already been sent."},
            status=200,
        )

    result = create_and_email_payment_receipt(payment)

    if result["email_sent"]:
        return Response(
            {
                "message": "Payment receipt email sent successfully.",
                "email_sent": True,
            },
            status=200,
        )

    return Response(
        {
            "message": "Receipt email could not be sent. Please try again.",
            "email_sent": False,
            "pdf_available": result["pdf_available"],
        },
        status=502,
    )
