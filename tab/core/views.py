from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

import log

from .helpers import (
    generate_otp,
    get_or_create_user,
    has_organization_email_domain,
    send_otp_email,
)


def _get_safe_next_url(request: HttpRequest) -> str | None:
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def login(request: HttpRequest) -> HttpResponse:
    if request.method == "GET" and (otp := request.GET.get("otp")):
        params = {"otp": otp}
        if next_url := _get_safe_next_url(request):
            params["next"] = next_url
        query = urlencode(params)
        url = reverse("verify")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    if request.method == "POST":
        email: str = request.POST["email"]
        if not has_organization_email_domain(email):
            messages.error(request, "No organization found for that email domain.")
            return redirect("login")

        log.info(f"Sending OTP to {email}")
        otp = generate_otp()
        cache.set(f"otp:{email}", otp, timeout=60 * 10)
        send_otp_email(email, otp)
        request.session["email"] = email

        url = reverse("verify")
        if next_url := _get_safe_next_url(request):
            url += f"?{urlencode({'next': next_url})}"
        return redirect(url)

    context = {
        "authentik_enabled": bool(settings.OIDC_RP_CLIENT_ID),
        "email_enabled": bool(settings.POSTMARK_API_KEY),
    }
    return render(request, "core/login.html", context)


def verify(request: HttpRequest) -> HttpResponse:
    email = request.session.get("email")
    if not email:
        messages.error(request, "Please enter your email address first.")
        return redirect("login")

    if request.method == "POST":
        submitted_otp = request.POST.get("otp", "")
        log.info(f"Verifying OTP for {email}")
        stored_otp = cache.get(f"otp:{email}")

        if stored_otp and submitted_otp == stored_otp:
            user = get_or_create_user(email)
            auth_login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            cache.delete(f"otp:{email}")
            request.session.pop("email", None)
            url = _get_safe_next_url(request) or "/"
            return redirect(url)
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            context = {"email": email, "otp_value": submitted_otp}
            return render(request, "core/verify.html", context)

    context = {"email": email, "otp_value": request.GET.get("otp")}
    return render(request, "core/verify.html", context)


def logout(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("/")


def ping(request: HttpRequest) -> HttpResponse:
    probe = request.GET.get("probe")

    if probe == "liveness":
        return HttpResponse("alive")

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        return HttpResponse(f"Database error: {str(e)}", status=500)

    if probe == "startup":
        return HttpResponse("started")
    elif probe == "readiness":
        return HttpResponse("ready")
    else:
        return HttpResponse("pong")
