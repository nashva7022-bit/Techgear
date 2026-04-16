import random
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
from .models import OTP


def generate_and_send_otp(user, email):
    otp = str(random.randint(100000, 999999))

    OTP.objects.create(
        user=user,
        otp=make_password(otp)
    )

    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP is {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        fail_silently=False,
    )