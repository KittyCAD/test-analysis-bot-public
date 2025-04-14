from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from django_tables2 import RequestConfig

from .models import Project
from .tables import TestTable


def index(_request):
    return redirect(reverse("admin:index"))


def detail(request, path: str):
    project = get_object_or_404(Project, repository__iendswith=path.strip("/"))
    table = TestTable(project.test_set.all())
    RequestConfig(request).configure(table)

    return render(
        request,
        "projects/tests.html",
        {
            "project": project,
            "table": table,
        },
    )
