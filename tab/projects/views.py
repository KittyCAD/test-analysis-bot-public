from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .models import Project


def index(_request):
    return redirect(reverse("admin:index"))


def detail(_request, path: str):
    project = get_object_or_404(Project, repository__iendswith=path)
    url = reverse("admin:projects_project_change", args=[project.id])
    return redirect(url)
