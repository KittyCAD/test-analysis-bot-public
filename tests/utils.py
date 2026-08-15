from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore

from playwright.sync_api import Page
from pytest_django.live_server_helper import LiveServer

SNAPSHOT_DIR = Path("tests/snapshots")


def force_login(page: Page, live_server: LiveServer, user: User):
    session = SessionStore()
    session["_auth_user_id"] = str(user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session.save()
    assert session.session_key is not None
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session.session_key,
                "url": live_server.url,
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )


def take_snapshot(page: Page, name: str):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=SNAPSHOT_DIR / f"{name}.png", full_page=True)
