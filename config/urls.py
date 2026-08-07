from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", lambda _request: redirect("projects:index")),
    path("", include("tab.core.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("projects/", include("tab.projects.urls", namespace="projects")),
    path("releases/", include("tab.releases.urls", namespace="releases")),
    path("api/", include("tab.api.urls")),
    path("admin/", admin.site.urls),
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=staticfiles_storage.url("favicon/favicon.ico"),
            permanent=True,
        ),
    ),
]
if settings.DEBUG:
    urlpatterns = [
        path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ] + urlpatterns
