from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

import log

from .helpers import generate_otp, get_or_create_user, send_otp_email
from .models import Organization


def login(request: HttpRequest) -> HttpResponse:
    if request.method == "GET" and (otp := request.GET.get("otp")):
        params = {"otp": otp}
        if next_url := request.GET.get("next"):
            params["next"] = next_url
        query = urlencode(params)
        url = reverse("verify")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    if request.method == "POST":
        email: str = request.POST["email"]
        domain = email.split("@")[1]
        if not Organization.objects.filter(email_domain__iexact=domain).exists():
            messages.error(request, "No organization found for that email domain.")
            return redirect("login")

        log.info(f"Sending OTP to {email}")
        otp = generate_otp()
        cache.set(f"otp:{email}", otp, timeout=60 * 10)
        send_otp_email(email, otp)
        request.session["email"] = email

        url = reverse("verify")
        if next := request.GET.get("next"):
            url += f"?next={next}"
        return redirect(url)

    return render(request, "core/login.html")


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
            auth_login(request, user)
            cache.delete(f"otp:{email}")
            request.session.pop("email", None)
            url = request.GET.get("next", "/")
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
