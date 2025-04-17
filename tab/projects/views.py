from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView

from django_tables2 import SingleTableMixin

from .models import Project, Result, Status, Test
from .tables import ResultTable, TestResultTable, TestTable


def index(request):
    return render(request, "projects/index.html")


class TestsListView(SingleTableMixin, ListView):
    model = Test
    table_class = TestTable
    template_name = "projects/tests.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        search = self.request.GET.get("search")
        enabled = self.request.GET.get("enabled")

        queryset = project.tests.select_related("last_result")
        if search:
            queryset = queryset.filter(name__icontains=search)
        if enabled is None or enabled == "true":
            queryset = queryset.filter(enabled=True)
        if project.test_inactive_threshold:
            queryset = queryset.filter(
                updated_at__gte=timezone.now() - project.test_inactive_threshold
            )

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


class ResultsListView(SingleTableMixin, ListView):
    model = Result
    table_class = ResultTable
    template_name = "projects/results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        branch = self.request.GET.get("branch", "all")
        show = self.request.GET.get("show", "all")
        search = self.request.GET.get("search")

        queryset = (
            Result.objects.filter(test__project=project)
            .annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F("test")],
                    order_by=F("created_at").desc(),
                )
            )
            .filter(row_number=1)
            .order_by("-created_at")
            .select_related("test", "test__project")
        )
        if branch != "all":
            queryset = queryset.filter(branch=branch)
        if show == "bad":
            queryset = queryset.exclude(status__in=[Status.PASSED, Status.SKIPPED])
        elif show == "good":
            queryset = queryset.filter(status__in=[Status.PASSED, Status.SKIPPED])
        if search:
            queryset = queryset.filter(test__name__icontains=search)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["project"] = project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        context["branch"] = self.request.GET.get("branch", "all")
        context["show"] = self.request.GET.get("show", "all")
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                # TODO: Link to results for this particular project instead
                "admin:projects_project_change",
                args=[project.pk],
            )

        return context


class TestResultsListView(SingleTableMixin, ListView):
    model = Result
    table_class = TestResultTable
    template_name = "projects/test-results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        branch = self.request.GET.get("branch")
        show = self.request.GET.get("show", "all")
        status = self.request.GET.get("status")

        if branch == "all":
            queryset = test.results.all()
        elif branch:
            queryset = test.results.filter(branch=branch)
        else:
            queryset = test.results.filter(branch__in=test.significant_branches)
        if show == "bad":
            queryset = queryset.exclude(status__in=[Status.PASSED, Status.SKIPPED])
        elif show == "good":
            queryset = queryset.filter(status__in=[Status.PASSED, Status.SKIPPED])
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        context["project"] = project
        context["test"] = test
        context["branch"] = self.request.GET.get("branch")
        context["show"] = self.request.GET.get("show", "all")
        if self.request.user.is_staff:
            context["admin_url"] = reverse("admin:projects_test_change", args=[test.pk])

        return context
