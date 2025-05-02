from django.contrib.auth.models import User

import log


def get_or_create_user(email: str) -> User:
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        log.warning(f"User {email} does not exist, creating it automatically")
        username = email.lower().split("@")[0]
        return User.objects.create_user(username=username, email=email.lower())
