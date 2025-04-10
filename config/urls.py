from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("", lambda request: redirect("projects:index")),
    path("projects/", include("tab.projects.urls", namespace="projects")),
    path("api/", include("tab.api.urls")),
    path("admin/", admin.site.urls),
]
if settings.DEBUG:
    urlpatterns = [
        path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ] + urlpatterns
