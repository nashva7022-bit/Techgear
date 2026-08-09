import random

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import OTP

OTP_PURPOSE_INFO = {
    "signup": ("complete your TechGear account signup", 2),
    "password_reset": ("reset your TechGear account password", 1),
    "email_change": ("confirm your new email address on TechGear", 1),
}


def generate_and_send_otp(user, email, purpose="signup"):
    otp = str(random.randint(100000, 999999))
    OTP.objects.create(user=user, otp=make_password(otp), purpose=purpose)

    action, expiry_minutes = OTP_PURPOSE_INFO.get(
        purpose, ("verify your TechGear account", 2)
    )
    expiry_word = "minute" if expiry_minutes == 1 else "minutes"

    context = {
        "user_name": user.first_name or user.username,
        "otp": otp,
        "action_text": action,
        "expiry_minutes": expiry_minutes,
        "expiry_word": expiry_word,
        "current_year": timezone.now().year,
    }

    text_body = (
        f"Hi {context['user_name']},\n\n"
        f"Use the code below to {action}:\n\n"
        f"    {otp}\n\n"
        f"This code expires in {expiry_minutes} {expiry_word}. "
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"- TechGear"
    )
    html_body = render_to_string("emails/otp_email.html", context)

    email_msg = EmailMultiAlternatives(
        subject="Your TechGear verification code",
        body=text_body,
        from_email=settings.EMAIL_HOST_USER,
        to=[email],
    )
    email_msg.attach_alternative(html_body, "text/html")
    email_msg.send(fail_silently=False)
