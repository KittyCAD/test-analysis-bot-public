from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, ListView

import log
from django_tables2 import SingleTableMixin

from tab.core.models import Organization

from .forms import BulkUpdateDisabledTestsForm
from .models import Project, Result, Status, Test
from .tables import DisabledTestTable, ResultTable, TestResultTable, TestTable


def index(request):
    if not request.user.is_authenticated:
        return render(request, "projects/index.html", {"projects": []})

    email_domain = request.user.email.split("@")[1]
    try:
        organization = Organization.objects.get(email_domain=email_domain)
        projects = Project.objects.filter(
            repository__startswith=organization.repository_index
        )
    except Organization.DoesNotExist:
        projects = Project.objects.none()

    return render(request, "projects/index.html", {"projects": projects})


class TestsView(SingleTableMixin, ListView):
    table_class = TestTable
    template_name = "projects/tests.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        search = self.request.GET.get("search", "").strip()
        enabled = self.request.GET.get("enabled", "true")

        queryset = project.tests.select_related("last_result")
        if search:
            queryset = queryset.filter(name__icontains=search)
        if enabled == "true":
            queryset = queryset.filter(enabled=True)
        elif enabled == "false":
            queryset = queryset.filter(enabled=False)
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
        context["search"] = self.request.GET.get("search", "").strip()
        context["enabled"] = self.request.GET.get("enabled", "true")
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                "admin:projects_project_change", args=[project.pk]
            )

        return context


class DisabledTestsView(SingleTableMixin, FormView):
    table_class = DisabledTestTable
    table_pagination = False
    template_name = "projects/tests-disabled.html"
    form_class = BulkUpdateDisabledTestsForm

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        search = self.request.GET.get("search", "").strip()

        queryset = project.tests.filter(
            enabled=False, last_result__isnull=False
        ).select_related("last_result", "disabled_user")
        if search:
            queryset = queryset.filter(name__icontains=search)
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
        context["disabled_only"] = True
        context["search"] = self.request.GET.get("search", "").strip()
        context["base_url"] = settings.BASE_URL
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                "admin:projects_project_change", args=[project.pk]
            )

        return context

    def form_valid(self, form):
        test_ids = form.cleaned_data["test_ids"].split(",")
        disabled = form.cleaned_data["disabled"]
        disabled_reason = form.cleaned_data["disabled_reason"]
        disabled_tracker = form.cleaned_data["disabled_tracker"]

        tests = self.get_queryset().filter(id__in=test_ids)
        for test in tests:
            test.disabled = disabled
            test.disabled_reason = disabled_reason
            test.disabled_tracker = disabled_tracker
            test.disabled_user = self.request.user
            if not disabled:
                test.disabled_platforms = []
                if test.last_result.status in {Status.SKIPPED, Status.DISABLED}:
                    # Modify status to hide it from this view
                    test.last_result.status = Status.INTERRUPTED
                    test.last_result.save()
            test.save()
        log.info(f"{self.request.user} updated {len(tests)} tests")

        redirect_url = self.request.path
        if search := self.request.GET.get("search"):
            redirect_url += f"?search={search}"

        return redirect(redirect_url)


class DisabledTestsRegexView(DisabledTestsView):
    def render_to_response(self, context, **response_kwargs):
        regex = "|".join(row.record.regex for row in context["table"].rows)
        return HttpResponse(f"'{regex}'", content_type="text/plain")


class ResultsView(SingleTableMixin, ListView):
    table_class = ResultTable
    template_name = "projects/results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        branch = self.request.GET.get("branch", project.default_branch)
        show = self.request.GET.get("show", "all")
        search = self.request.GET.get("search")

        queryset = Result.objects.filter(
            test__project=project, branch=branch
        ).select_related("test", "test__project")
        latest_commit = queryset.values_list("commit", flat=True).first()
        queryset = queryset.filter(commit=latest_commit)

        if show == "fails":
            queryset = queryset.exclude(
                status__in={Status.PASSED, Status.XFAILED, Status.SKIPPED}
            ).filter(final=True)
        if search:
            queryset = queryset.filter(test__name__icontains=search)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        branch = self.request.GET.get("branch", project.default_branch)
        commit = Result.objects.get_latest_commit(project, branch)

        context["project"] = project
        context["branch"] = branch
        context["merge_url"] = self._get_merge_url(project, branch)
        context["branches"] = self._get_active_branches(project)
        context["search"] = self.request.GET.get("search", "").strip()
        context["show"] = self.request.GET.get("show", "all")
        context["health"] = Result.objects.get_health(project, commit)
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                # TODO: Link to results for this particular project instead
                "admin:projects_project_change",
                args=[project.pk],
            )

        return context

    def _get_merge_url(self, project: Project, branch: str) -> str:
        result = (
            Result.objects.filter(
                test__project=project,
                branch=branch,
            )
            .order_by("-created_at")
            .first()
        )
        return result.merge_url if result else ""

    def _get_active_branches(self, project: Project) -> list[str]:
        results_by_branch = (
            Result.objects.filter(
                test__project=project,
            )
            .distinct()
            .order_by("branch")
        )
        if project.branch_inactive_threshold:
            results_by_branch = results_by_branch.filter(
                created_at__gte=timezone.now() - project.branch_inactive_threshold
            )
        return list(results_by_branch.values_list("branch", flat=True))


class TestResultsView(SingleTableMixin, ListView):
    table_class = TestResultTable
    template_name = "projects/test-results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        if branch := self.request.GET.get("branch"):
            branches = [branch] + test.significant_branches
        else:
            branches = test.significant_branches
        show = self.request.GET.get("show", "all")  # TODO: Expose filter in UI
        platform = self.request.GET.get("platform")  # TODO: Expose filter in UI

        queryset = test.results.filter(branch__in=branches)
        if show == "fails":
            queryset = queryset.exclude(
                status__in={
                    Status.PASSED,
                    Status.XPASSED,
                    Status.SKIPPED,
                    Status.DISABLED,
                }
            )
        if platform:
            queryset = queryset.filter(platform=platform)

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
