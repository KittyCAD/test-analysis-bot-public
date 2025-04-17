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

        search = self.request.GET.get("search", "")
        enabled = self.request.GET.get("enabled")

        queryset = project.tests.all().select_related("last_result")
        if search:
            queryset = queryset.filter(name__icontains=search)
        if enabled is None or enabled == "true":
            queryset = queryset.filter(enabled=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["project"] = project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        context["search"] = self.request.GET.get("search", "")
        context["enabled"] = self.request.GET.get("enabled", "true")
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                "admin:projects_project_change", args=[project.pk]
            )

        return context


class ResultListView(SingleTableMixin, ListView):
    model = Test
    table_class = ResultTable
    template_name = "projects/results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        branch = self.request.GET.get("branch")

        if branch == "all":
            queryset = test.results.all()
        elif branch:
            queryset = test.results.filter(branch=branch)
        else:
            queryset = test.results.filter(branch__in=test.significant_branches)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        context["project"] = project
        context["test"] = test
        if self.request.user.is_staff:
            context["admin_url"] = reverse("admin:projects_test_change", args=[test.pk])

        return context
