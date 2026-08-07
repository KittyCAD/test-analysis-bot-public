from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from .enums import Type
from .models import Environment, Release

GRAPH_ENVIRONMENT_TYPES = [choice for choice in Type if choice != Type.LOCAL]
GRAPH_ENVIRONMENT_COLUMNS = {
    choice.value: index for index, choice in enumerate(GRAPH_ENVIRONMENT_TYPES)
}


def _column_layout_meta(*, row_height: int = 110) -> dict:
    return {
        "layout": "columns",
        "rowHeight": row_height,
        "columns": [
            {
                "id": choice.value,
                "label": choice.label,
                "color": choice.color,
            }
            for choice in GRAPH_ENVIRONMENT_TYPES
        ],
    }


def build_environment_graph(environments: list[Environment]) -> dict:
    nodes = []
    edges = []
    ids = {environment.pk for environment in environments}

    for environment in environments:
        project_href = reverse("projects:tests", args=[environment.project.path])
        nodes.append(
            {
                "id": str(environment.pk),
                "label": environment.project.name,
                "subtitle": environment.url or "",
                "color": Type(environment.name).color,
                "projectHref": project_href,
                "href": environment.url or "",
                "column": GRAPH_ENVIRONMENT_COLUMNS.get(environment.name, 0),
            }
        )
        for dependency in environment.dependencies.all():
            if dependency.pk in ids:
                edges.append(
                    {
                        "id": f"e{environment.pk}-{dependency.pk}",
                        "source": str(environment.pk),
                        "target": str(dependency.pk),
                    }
                )

    return {
        **_column_layout_meta(),
        "nodes": nodes,
        "edges": edges,
    }


def build_release_graph(releases: list[Release], *, truncated: bool = False) -> dict:
    nodes = []
    edges = []
    ids = {release.pk for release in releases}

    for release in releases:
        environment = release.environment
        branch_commit = (
            f"{release.branch}@{release.commit_humanized}"
            if release.branch
            else release.commit_humanized
        )
        local_created = timezone.localtime(release.created_at)
        nodes.append(
            {
                "id": str(release.pk),
                "label": f"{environment.project.name}\n\n{branch_commit}",
                "subtitle": environment.url or "",
                "color": Type(environment.name).color,
                "projectHref": reverse(
                    "projects:tests", args=[environment.project.path]
                ),
                "href": release.commit_url or release.branch_url or "",
                "urlHref": environment.url or "",
                "column": GRAPH_ENVIRONMENT_COLUMNS.get(environment.name, 0),
                "columnId": environment.name,
                "createdAt": release.created_at.isoformat(),
                "createdLabel": local_created.strftime("%b %d, %H:%M"),
            }
        )
        for dependency in release.dependencies.all():
            if dependency.pk in ids:
                edges.append(
                    {
                        "id": f"e{release.pk}-{dependency.pk}",
                        "source": str(release.pk),
                        "target": str(dependency.pk),
                    }
                )

    return {
        **_column_layout_meta(row_height=130),
        "layout": "columns-timeline",
        "truncated": truncated,
        "nodes": nodes,
        "edges": edges,
    }
