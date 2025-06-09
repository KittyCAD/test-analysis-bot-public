from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render

import log

from .helpers import generate_otp, get_or_create_user, send_otp_email


def login(request):
    if request.method == "POST":
        if submitted_otp := request.POST.get("otp"):
            email = request.POST.get("email")
            log.info(f"Verifying OTP for {email}")
            stored_otp = cache.get(f"otp:{email}")
            if stored_otp and submitted_otp == stored_otp:
                user = get_or_create_user(email)
                auth_login(request, user)
                cache.delete(f"otp:{email}")
                return redirect("/")
            else:
                messages.error(request, "Invalid OTP. Please try again.")
                return render(request, "core/verify.html", {"email": email})
        else:
            email = request.POST.get("email")
            log.info(f"Sending OTP to {email}")
            otp = generate_otp()
            cache.set(f"otp:{email}", otp, timeout=600)
            send_otp_email(email, otp)
            return render(request, "core/verify.html", {"email": email})
    return render(request, "core/login.html")


def logout(request):
    auth_logout(request)
    return redirect("/")


def ping(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse("pong")
    except Exception as e:
        return HttpResponse(f"Database error: {str(e)}", status=500)
