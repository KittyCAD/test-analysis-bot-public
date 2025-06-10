from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView

import log
from django_tables2 import SingleTableMixin

from tab.core.helpers import get_or_create_user
from tab.core.models import Organization

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
            projects = Project.objects.filter(
                repository__startswith=organization.repository_index
            ).order_by("repository")
        except Organization.DoesNotExist:
            organization = None
            projects = Project.objects.none()

        context["projects"] = projects
        if self.request.user.is_staff and organization:
            context["admin_url"] = reverse(
                "admin:core_organization_change", args=[organization.pk]
            )

        return context


class TestsView(LoginRequiredMixin, SingleTableMixin, ListView):
    table_class = TestTable
    template_name = "projects/tests.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        search = self.request.GET.get("search", "").strip()
        enabled = self.request.GET.get("enabled", "true")

        queryset = project.tests.select_related("suite", "last_result")
        if search:
            queryset = queryset.filter(
                Q(suite__name__icontains=search) | Q(name__icontains=search)
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
        context["search"] = self.request.GET.get("search", "").strip()
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
            test.disabled = disabled
            test.disabled_reason = disabled_reason
            test.disabled_tracker = disabled_tracker
            test.disabled_user = disabled_user
            if not disabled:
                test.disabled_platforms = []
                if test.last_result.status in {Status.SKIPPED, Status.DISABLED}:
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


class ResultsView(LoginRequiredMixin, SingleTableMixin, ListView):
    table_class = ResultTable
    template_name = "projects/results.html"

    def get_queryset(self):
        project = get_object_or_404(
            Project, repository__iendswith=self.kwargs["path"].strip("/")
        )

        branch = self.request.GET.get("branch", project.default_branch)
        search = self.request.GET.get("search")
        platform = self.request.GET.get("platform")
        show = self.request.GET.get("show", "all")

        queryset = Result.objects.filter(
            test__project=project, branch=branch
        ).select_related("suite", "test", "test__project", "test__suite")
        latest_commit = queryset.values_list("commit", flat=True).first()
        queryset = queryset.filter(commit=latest_commit)

        if search:
            queryset = queryset.filter(
                Q(suite__name__icontains=search) | Q(test__name__icontains=search)
            )
        if platform:
            queryset = queryset.filter(platform=platform)
        if show == "fails":
            queryset = queryset.exclude(
                status__in={Status.PASSED, Status.XFAILED, Status.SKIPPED}
            ).filter(final=True)

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
        context["platform"] = self.request.GET.get("platform", "").strip()
        context["show"] = self.request.GET.get("show", "all")
        context["health"] = Result.objects.get_health(project, commit)
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

        if "expand" in self.request.GET:
            expand = self.request.GET["expand"] == "true"
        else:
            expand = bool(test.last_result) and test.failure_rate > 0.25

        context["project"] = project
        context["test"] = test
        context["expand"] = expand
        context["branch"] = self.request.GET.get("branch")
        context["platform"] = self.request.GET.get("platform", "").strip()
        context["show"] = self.request.GET.get("show", "all")
        for name in ["failure_rate", "block_rate", "enabled"]:
            field = test._meta.get_field(name)
            assert isinstance(field, models.Field), f"Unknown field: {name}"
            context[f"{field.name}_help"] = field.help_text
        if self.request.user.is_staff:
            context["admin_url"] = reverse("admin:projects_test_change", args=[test.pk])

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
            "disabled": test.disabled,
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

        test.disabled = form.cleaned_data["disabled"]
        test.disabled_reason = form.cleaned_data["disabled_reason"]
        test.disabled_tracker = form.cleaned_data["disabled_tracker"]
        test.disabled_user = get_or_create_user(form.cleaned_data["disabled_user"])
        if test.disabled:
            test.disabled_platforms = []
        test.save()

        log.info(f"{self.request.user} updated test {test.name}")
        modified = "disabled from" if test.disabled else "allowed to"
        messages.success(self.request, f"Test is now {modified} blocking merges.")

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
