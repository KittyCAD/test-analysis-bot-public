from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from django_tables2 import RequestConfig

from .models import Project, Test
from .tables import ResultTable, TestTable


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


def test_detail(request, path: str, test_id: int):
    project = get_object_or_404(Project, repository__iendswith=path.strip("/"))
    test = get_object_or_404(Test, project=project, id=test_id)
    table = ResultTable(test.result_set.filter(branch__in=test.relevant_branches))
    RequestConfig(request).configure(table)

    return render(
        request,
        "projects/results.html",
        {"project": project, "test": test, "table": table},
    )
