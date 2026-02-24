import random
import string
from contextlib import suppress

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.urls import reverse

import log

from .constants import TEST_OTP


def get_or_create_user(email: str) -> User:
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        log.warning(f"User {email} does not exist, creating it automatically")
        username = base_username = email.lower().split("@")[0]
        for count in range(1, 10):
            if count > 1:
                username = f"{base_username}{count}"
            with suppress(IntegrityError):
                return User.objects.create_user(username=username, email=email.lower())
    raise ValueError(f"Unable to generate username for {email}")


def generate_otp() -> str:
    if hasattr(settings, "TEST"):
        log.warning("Bypassing OTP generation for tests")
        return TEST_OTP
    return "".join(random.choices(string.digits, k=6))


def send_otp_email(email: str, otp: str):
    subject = "Your login code"
    html = render_to_string(
        "core/emails/otp.html",
        {
            "otp": otp,
            "login_url": f"{settings.BASE_URL}{reverse('login')}?otp={otp}",
        },
    )
    from_email = "Test Analysis Bot <no-reply@zoo.dev>"
    message = EmailMessage(subject, html, from_email, [email])
    message.content_subtype = "html"
    message.send()
