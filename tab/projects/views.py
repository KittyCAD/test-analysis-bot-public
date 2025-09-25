import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

import log
from django_tables2 import SingleTableMixin

from tab.core.helpers import get_or_create_user
from tab.core.models import Organization

from .constants import FAILURE_RATE_EPSILON
from .forms import BulkUpdateTestForm, UpdateTestForm
from .helpers import get_disabled_test_metrics
from .models import Project, Result, Status, Test
from .tables import DisabledTestTable, ResultTable, TestResultTable, TestTable


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "projects/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        assert self.request.user.is_authenticated
        email_domain = self.request.user.email.split("@")[1]
        try:
            organization = Organization.objects.get(email_domain=email_domain)
            projects = (
                Project.objects.filter(
                    repository__startswith=organization.repository_index
                )
                .annotate(
                    suites_count=Count("suites", distinct=True),
                    tests_count=Count("tests"),
                )
                .order_by("repository")
            )
        except Organization.DoesNotExist:
            organization = None
            projects = Project.objects.none()

        context["projects"] = projects
        if self.request.user.is_staff and organization:
            context["admin_url"] = reverse(
                "admin:core_organization_change", args=[organization.pk]
            )

        return context


class SearchLabelMixin:
    search_labels: list[str] = []

    def dispatch(self, request, *args, **kwargs):
        if search := request.GET.get("search", "").strip():
            params = request.GET.copy()
            updated = False
            # Convert certain search terms to dedicated query params
            for label in self.search_labels:
                if match := re.search(rf"{label}:(\S+)", search, re.IGNORECASE):
                    value = match.group(1).lower().strip("@")
                    log.info(f"Converting '{label}:{value}' search to query param")
                    search = (
                        re.sub(rf"{label}:\S+", "", search, flags=re.IGNORECASE)
                        .replace("  ", " ")
                        .strip()
                    )
                    params[label] = value
                    updated = True
            # Redirect to new URL with dedicated query params
            if updated:
                if search:
                    params["search"] = search
                else:
                    params.pop("search", None)
                log.info(f"Redirecting with '?{params.urlencode()}'")
                return redirect(f"{request.path}?{params.urlencode()}")
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]


class TestsView(LoginRequiredMixin, SingleTableMixin, SearchLabelMixin, ListView):
    table_class = TestTable
    template_name = "projects/tests.html"
    search_labels = ["tag"]

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        suite_id = self.kwargs.get("suite_id")
        search = self.request.GET.get("search", "").strip()
        tag = self.request.GET.get("tag")
        enabled = self.request.GET.get("enabled", "true")

        queryset = project.tests.select_related(
            "suite", "last_result"
        ).prefetch_related("project__suites")
        if suite_id:
            queryset = queryset.filter(suite_id=suite_id)
        if search:
            queryset = queryset.filter(
                Q(suite__name__icontains=search) | Q(name__icontains=search)
            )
        if tag:
            queryset = queryset.filter(
                Q(last_result__metadata__tags__icontains=tag)
                | Q(last_result__metadata__tags__icontains=f"@{tag}")
            )
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
        context["suites"] = project.suites.all()
        context["suite_id"] = self.kwargs.get("suite_id")
        context["search"] = self.request.GET.get("search", "").strip()
        context["tag"] = self.request.GET.get("tag", "").strip()
        context["enabled"] = self.request.GET.get("enabled", "true")
        if self.request.user.is_staff:
            context["admin_url"] = reverse(
                "admin:projects_project_change", args=[project.pk]
            )

        return context


class DisabledTestsView(LoginRequiredMixin, SingleTableMixin, FormView):
    table_class = DisabledTestTable
    table_pagination = False
    template_name = "projects/tests-disabled.html"
    form_class = BulkUpdateTestForm

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        search = self.request.GET.get("search", "").strip()
        tracker = self.request.GET.get("tracker", "").strip()

        queryset = project.tests.filter(
            enabled=False, last_result__isnull=False
        ).select_related("suite", "last_result", "disabled_user")
        if search:
            queryset = queryset.filter(
                Q(suite__name__icontains=search)
                | Q(name__icontains=search)
                | Q(disabled_reason__icontains=search)
                | Q(disabled_tracker__icontains=search)
                | Q(disabled_user__email__icontains=search)
            )
        if tracker == "true":
            queryset = queryset.exclude(disabled_tracker__isnull=True)
        elif tracker == "false":
            queryset = queryset.filter(disabled_tracker__isnull=True)
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

    def get_initial(self):
        tests = self.get_queryset()
        initial = {
            "disabled_user": (
                self.request.user.email if self.request.user.is_authenticated else ""
            ),
        }
        emails = set(t.disabled_user.email for t in tests if t.disabled_user)
        if len(emails) == 1:
            initial["disabled_user"] = emails.pop()
        reasons = set(t.disabled_reason for t in tests)
        if len(reasons) == 1:
            initial["disabled_reason"] = reasons.pop()
        trackers = set(t.disabled_tracker for t in tests)
        if len(trackers) == 1:
            initial["disabled_tracker"] = trackers.pop()
        return initial

    def form_valid(self, form):
        test_ids = form.cleaned_data["test_ids"].split(",")
        disabled = form.cleaned_data["disabled"]
        disabled_reason = form.cleaned_data["disabled_reason"]
        disabled_tracker = form.cleaned_data["disabled_tracker"]
        disabled_user = get_or_create_user(form.cleaned_data["disabled_user"])

        tests = self.get_queryset().filter(id__in=test_ids)
        for test in tests:
            test.disabled_at = timezone.now() if disabled else None
            test.disabled_reason = disabled_reason
            test.disabled_tracker = disabled_tracker
            test.disabled_user = disabled_user
            if not disabled:
                test.disabled_platforms = []
                if test.last_result.status in Status.test_disabled():
                    # Modify status to hide it from this view
                    test.last_result.status = Status.INTERRUPTED
                    test.last_result.save()
            test.save()

        log.info(f"{self.request.user} updated {len(tests)} tests")
        s = "" if len(tests) == 1 else "s"
        messages.success(self.request, f"Successfully updated {len(tests)} test{s}.")

        redirect_url = self.request.path
        if search := self.request.GET.get("search"):
            redirect_url += f"?search={search}"

        return redirect(redirect_url)


class DisabledTestsRegexView(DisabledTestsView):
    def dispatch(self, request, *args, **kwargs):
        """Disable authentication for this view to work with local test runners."""
        return super(FormView, self).dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        regex = "|".join(row.record.regex for row in context["table"].rows)
        return HttpResponse(f"'{regex}'", content_type="text/plain")


class ResultsView(LoginRequiredMixin, SingleTableMixin, SearchLabelMixin, ListView):
    table_class = ResultTable
    template_name = "projects/results.html"
    search_labels = ["platform", "tag"]

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        branch = self.request.GET.get("branch", project.default_branch)
        suite_id = self.kwargs.get("suite_id")
        search = self.request.GET.get("search")
        platform = self.request.GET.get("platform")
        tag = self.request.GET.get("tag")
        show = self.request.GET.get("show", "all")

        queryset = (
            Result.objects.filter(test__project=project, branch=branch)
            .select_related("suite", "test", "test__project", "test__suite")
            .prefetch_related("test__project__suites")
        )
        latest_commit = queryset.values_list("commit", flat=True).first()
        queryset = queryset.filter(commit=latest_commit)

        if suite_id:
            queryset = queryset.filter(suite_id=suite_id)
        if search:
            queryset = queryset.filter(
                Q(suite__name__icontains=search) | Q(test__name__icontains=search)
            )
        if platform:
            queryset = queryset.filter(platform=platform)
        if tag:
            queryset = queryset.filter(
                Q(metadata__tags__icontains=tag)
                | Q(metadata__tags__icontains=f"@{tag}")
            )
        if show == "fails":
            queryset = queryset.exclude(status__in=Status.merge_allowed()).filter(
                final=True
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        branch = self.request.GET.get("branch", project.default_branch)

        context["project"] = project
        context["branch"] = branch
        context["merge_url"] = self._get_merge_url(project, branch)
        context["branches"] = self._get_active_branches(project)
        context["suites"] = project.suites.all()
        context["suite_id"] = self.kwargs.get("suite_id")
        context["search"] = self.request.GET.get("search", "").strip()
        context["platform"] = self.request.GET.get("platform", "").strip()
        context["tag"] = self.request.GET.get("tag", "").strip()
        context["show"] = self.request.GET.get("show", "all")
        context["base_url"] = settings.BASE_URL
        if self.request.user.is_staff:
            context["admin_url"] = (
                reverse(
                    "admin:projects_result_changelist",
                )
                + f"?test__project__repository={project.repository}"
            )

        return context

    def _get_merge_url(self, project: Project, branch: str) -> str:
        result = (
            Result.objects.filter(
                test__project=project,
                branch=branch,
            )
            .select_related("test__project")
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


class ResultsRegexView(ResultsView):
    def dispatch(self, request, *args, **kwargs):
        """Disable authentication for this view to work with local test runners."""
        return super(ListView, self).dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        regex = "|".join(row.record.test.regex for row in context["table"].rows)
        return HttpResponse(f"'{regex}'", content_type="text/plain")


class TestResultsView(LoginRequiredMixin, SingleTableMixin, FormView):
    table_class = TestResultTable
    template_name = "projects/test-results.html"
    form_class = UpdateTestForm

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        branch = self.request.GET.get("branch")
        show = self.request.GET.get("show", "all")  # TODO: Expose filter in UI
        platform = self.request.GET.get("platform")

        queryset = Result.objects.filter_with_default_branches(test, branch)
        if show == "fails":
            queryset = queryset.exclude(status__in=Status.merge_allowed())
        if platform:
            queryset = queryset.filter(platform=platform)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )
        test = get_object_or_404(Test, project=project, id=self.kwargs["test_id"])

        if "expand" in self.request.GET:
            expand = self.request.GET["expand"] == "true"
        else:
            expand = bool(test.last_result) and test.failure_rate > 0.25
        if "weeks" in self.request.GET:
            weeks = float(self.request.GET["weeks"])
            expand = True
        else:
            weeks = 1.5

        context["project"] = project
        context["test"] = test
        context["expand"] = expand
        context["branch"] = self.request.GET.get("branch")
        context["platform"] = self.request.GET.get("platform", "").strip()
        context["show"] = self.request.GET.get("show", "all")
        context["history_data"] = test.history.get_data(test, weeks)
        for field in test._meta.get_fields():
            if hasattr(field, "help_text") and field.help_text:
                context[f"{field.name}_help"] = field.help_text
        if self.request.user.is_staff:
            context["admin_url"] = reverse("admin:projects_test_change", args=[test.pk])
            if test.suite:
                context["suite_admin_url"] = reverse(
                    "admin:projects_suite_change", args=[test.suite.pk]
                )

        return context

    def get_initial(self):
        test = get_object_or_404(
            Test,
            project__repository__iendswith=self.kwargs["path"].strip("/"),
            id=self.kwargs["test_id"],
        )
        original_email = test.disabled_user.email if test.disabled_user else ""
        current_email = (
            self.request.user.email if self.request.user.is_authenticated else ""
        )
        return {
            "test_id": test.id,
            "disabled": bool(test.disabled_at),
            "disabled_reason": test.disabled_reason,
            "disabled_tracker": test.disabled_tracker,
            "disabled_user": original_email or current_email,
        }

    def form_valid(self, form):
        test = get_object_or_404(
            Test,
            project__repository__iendswith=self.kwargs["path"].strip("/"),
            id=self.kwargs["test_id"],
        )
        previously_disabled = bool(test.disabled_at)

        test.disabled_at = timezone.now() if form.cleaned_data["disabled"] else None
        test.disabled_reason = form.cleaned_data["disabled_reason"]
        test.disabled_tracker = form.cleaned_data["disabled_tracker"]
        test.disabled_user = get_or_create_user(form.cleaned_data["disabled_user"])
        if test.disabled_at:
            test.disabled_platforms = []
        test.failure_rate += FAILURE_RATE_EPSILON  # prevent from being restored on save
        test.save()

        log.info(f"{self.request.user} updated test {test.name}")
        blocking = "disabled from blocking" if test.disabled_at else "allowed to block"
        if bool(test.disabled_at) != previously_disabled:
            blocking = "now " + blocking
        messages.success(self.request, f"Test is {blocking} merges.")

        redirect_url = self.request.path
        if branch := self.request.GET.get("branch"):
            redirect_url += f"?branch={branch}"

        return redirect(redirect_url)


class MetricsView(LoginRequiredMixin, TemplateView):
    template_name = "projects/metrics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        context["project"] = project
        context["disabled_test_metrics"] = get_disabled_test_metrics(project)
        if self.request.user.is_staff:
            context["admin_url"] = (
                reverse(
                    "admin:projects_test_changelist",
                )
                + f"?project__repository={project.repository}"
            )

        return context
