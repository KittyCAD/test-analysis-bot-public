from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from tab.core.models import Organization

from .constants import CHANGE_HISTORY_LIMIT
from .enums import Type
from .helpers import build_environment_graph, build_release_graph
from .models import Environment, Release


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "releases/list.html"

    def get_organization(self) -> Organization | None:
        assert self.request.user.is_authenticated
        email_domain = self.request.user.email.split("@")[1]
        try:
            return Organization.objects.get(email_domain=email_domain)
        except Organization.DoesNotExist:
            return None

    def get_history_limit(self) -> int:
        raw = self.request.GET.get("limit")
        if raw is None:
            return CHANGE_HISTORY_LIMIT
        try:
            return max(1, min(int(raw), 500))
        except (TypeError, ValueError):
            return CHANGE_HISTORY_LIMIT

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        show_review = self.request.GET.get("review") in ("true", "1")
        show_lines = self.request.GET.get("lines", "true") not in ("false", "0")
        limit = self.get_history_limit()
        truncated = False

        if organization is None:
            environments: list[Environment] = []
            releases: list[Release] = []
        else:
            environments = list(Environment.objects.filter_promotable(organization))
            releases_qs = Release.objects.filter(
                environment__project__repository__startswith=organization.repository_index
            ).exclude(environment__name=Type.LOCAL)
            if not show_review:
                releases_qs = releases_qs.exclude(environment__name=Type.REVIEW)
            # Fetch one extra row to detect whether the chart is truncated.
            releases = list(
                releases_qs.select_related("environment__project").prefetch_related(
                    "dependencies"
                )[: limit + 1]
            )
            truncated = len(releases) > limit
            releases = releases[:limit]

        context["show_review"] = show_review
        context["show_lines"] = show_lines
        context["history_limit"] = limit
        context["release_graph_truncated"] = truncated
        context["environment_graph"] = build_environment_graph(environments)
        context["release_graph"] = build_release_graph(
            releases, truncated=truncated, include_review=show_review
        )
        if self.request.user.is_staff:
            context["admin_url"] = reverse("admin:releases_environment_changelist")
        return context
