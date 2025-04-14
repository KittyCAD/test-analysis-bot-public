from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView

from django_tables2 import RequestConfig, SingleTableMixin

from .models import Project, Test
from .tables import ResultTable, TestTable


def index(request):
    return render(request, "projects/index.html")


class TestListView(SingleTableMixin, ListView):
    model = Test
    table_class = TestTable
    template_name = "projects/tests.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        queryset = project.test_set.all()
        search = self.request.GET.get("search", "")
        if search:
            queryset = queryset.filter(name__icontains=search)
        enabled = self.request.GET.get("enabled")
        if enabled is None or enabled == "true":
            queryset = queryset.filter(enabled=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        context["search"] = self.request.GET.get("search", "")
        context["enabled"] = self.request.GET.get("enabled", "true")
        return context


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
