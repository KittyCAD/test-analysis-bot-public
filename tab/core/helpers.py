import random
import string
from contextlib import suppress

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import IntegrityError

import log

from .constants import TEST_OTP


def get_or_create_user(email: str) -> User:
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        log.warning(f"User {email} does not exist, creating it automatically")
        username = email.lower().split("@")[0]
        for count in range(10):
            if count > 1:
                username = f"{username}{count}"
        with suppress(IntegrityError):
            return User.objects.create_user(username=username, email=email.lower())
    raise ValueError(f"Unable to generate username for {email}")


def generate_otp() -> str:
    if hasattr(settings, "TEST"):
        log.warning("Bypassing OTP generation for tests")
        return TEST_OTP
    return "".join(random.choices(string.digits, k=6))


def send_otp_email(email: str, otp: str):
    subject = "Test Analysis Bot"
    message = f"Your one-time password is: {otp}"
    from_email = "tab@zoo.dev"
    recipient_list = [email]
    send_mail(subject, message, from_email, recipient_list)
