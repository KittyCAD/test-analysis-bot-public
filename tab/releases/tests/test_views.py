from django.urls import reverse
from django.utils import timezone

import pytest

from tab.core.models import Organization
from tab.projects.models import Project
from tab.releases.enums import Type
from tab.releases.helpers import build_environment_graph, build_release_graph
from tab.releases.models import Environment, Release


@pytest.fixture
def organization():
    return Organization.objects.create(
        name="Test Org",
        email_domain="example.com",
        repository_index="https://github.com/foo",
    )


@pytest.fixture
def project(organization: Organization):
    return Project.objects.create(repository="https://github.com/foo/bar")


@pytest.fixture
def environment(project: Project):
    return Environment.objects.create(
        project=project,
        name=Type.STAGING,
        url="https://staging.example.com",
    )


@pytest.fixture
def release(environment: Environment):
    return Release.objects.create(
        environment=environment,
        branch="main",
        commit="abc1234deadbeef",
        tested_at=timezone.now(),
    )


def describe_graph_helpers(expect):
    @pytest.mark.django_db
    def it_builds_environment_dependency_edges(project: Project):
        api = Environment.objects.create(
            project=project, name=Type.PRODUCTION, url="https://api.example.com"
        )
        app = Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        app.dependencies.add(api)

        graph = build_environment_graph([api, app])
        expect(len(graph["nodes"])) == 2
        expect(len(graph["edges"])) == 1
        expect(graph["layout"]) == "columns"
        expect([column["id"] for column in graph["columns"]]) == [
            "review",
            "staging",
            "production",
        ]
        expect(graph["edges"][0]["source"]) == str(app.pk)
        expect(graph["edges"][0]["target"]) == str(api.pk)
        by_id = {node["id"]: node for node in graph["nodes"]}
        expect(by_id[str(app.pk)]["column"]) == 1
        expect(by_id[str(api.pk)]["column"]) == 2

    @pytest.mark.django_db
    def it_builds_release_nodes_with_timestamps(project: Project):
        api_env = Environment.objects.create(
            project=project, name=Type.PRODUCTION, url="https://api.example.com"
        )
        app_env = Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        api_release = Release.objects.create(
            environment=api_env,
            branch="main",
            commit="1111111",
            tested_at=timezone.now(),
            finalized_at=timezone.now(),
        )
        app_release = Release.objects.create(
            environment=app_env, branch="main", commit="2222222"
        )
        app_release.dependencies.add(api_release)

        graph = build_release_graph([api_release, app_release])
        expect(graph["layout"]) == "columns-timeline"
        expect([column["id"] for column in graph["columns"]]) == ["deployed"]
        expect(len(graph["nodes"])) == 2
        expect(graph["edges"][0]["source"]) == str(app_release.pk)
        expect(graph["edges"][0]["target"]) == str(api_release.pk)
        by_id = {node["id"]: node for node in graph["nodes"]}
        expect(by_id[str(app_release.pk)]["column"]) == 0
        expect(by_id[str(api_release.pk)]["column"]) == 0
        expect(by_id[str(app_release.pk)]["columnId"]) == "deployed"
        expect(by_id[str(api_release.pk)]["columnId"]) == "deployed"
        expect(by_id[str(app_release.pk)]["createdAt"]).contains("T")
        label = by_id[str(app_release.pk)]["label"]
        expect(label).contains(project.name)
        expect(label).contains("main@2222222")
        expect(label).excludes("tested")
        expect(label).excludes("finalized")

    @pytest.mark.django_db
    def it_keeps_review_column_when_excluded(project: Project):
        staging = Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        release = Release.objects.create(
            environment=staging, branch="main", commit="3333333"
        )

        graph = build_release_graph([release])
        by_id = {column["id"]: column for column in graph["columns"]}
        expect([column["id"] for column in graph["columns"]]) == ["deployed"]
        expect(by_id["deployed"]["color"]) == Type.PRODUCTION.color
        expect(graph["nodes"][0]["column"]) == 0
        expect(graph["nodes"][0]["columnId"]) == "deployed"

    @pytest.mark.django_db
    def it_adds_review_lane_when_included(project: Project):
        staging = Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        review = Environment.objects.create(
            project=project, name=Type.REVIEW, url="https://app-pr-1.example.com"
        )
        staging_release = Release.objects.create(
            environment=staging, branch="main", commit="3333333"
        )
        review_release = Release.objects.create(
            environment=review, branch="feature", commit="reviewdeadbeef"
        )

        graph = build_release_graph(
            [staging_release, review_release], include_review=True
        )
        expect([column["id"] for column in graph["columns"]]) == [
            "review",
            "deployed",
        ]
        by_id = {node["id"]: node for node in graph["nodes"]}
        expect(by_id[str(review_release.pk)]["column"]) == 0
        expect(by_id[str(review_release.pk)]["columnId"]) == "review"
        expect(by_id[str(staging_release.pk)]["column"]) == 1
        expect(by_id[str(staging_release.pk)]["columnId"]) == "deployed"


def describe_releases_page(expect, admin_client, organization: Organization):
    @pytest.mark.django_db
    def it_renders_environments_then_releases(
        environment: Environment, release: Release
    ):
        response = admin_client.get(reverse("releases:index"))
        html = response.content.decode("utf-8")
        expect(response.status_code) == 200
        expect(html).contains("Environment Dependencies")
        expect(html).contains("Change History")
        expect(html).contains("environment-graph-data")
        expect(html).contains("release-graph-data")
        expect(html).contains("show-review-releases")
        expect(html).contains("Include review environments")
        expect(html).contains("show-dependency-lines")
        expect(html).contains("Show dependency lines")
        expect(response.context["show_review"]) == False
        expect(response.context["show_lines"]) == True
        expect(response.context["history_limit"]) == 50
        hidden_lines = admin_client.get(reverse("releases:index"), {"lines": "false"})
        expect(hidden_lines.context["show_lines"]) == False
        expect(
            [column["id"] for column in response.context["release_graph"]["columns"]]
        ) == ["deployed"]
        expect(
            [
                column["id"]
                for column in response.context["environment_graph"]["columns"]
            ]
        ) == [
            "review",
            "staging",
            "production",
        ]
        expect(html).contains(r"foo \u203a bar")
        expect(html).contains("main@abc1234")
        expect(html).contains("createdAt")
        expect(html).contains("columnId")
        expect(response.context["history_limit"]) == 50
        expect(response.context["release_graph_truncated"]) == False
        expect(html).excludes("releases-graph-truncated")
        expect(html).excludes("nav-tabs")

    @pytest.mark.django_db
    def it_limits_change_history_and_fades_when_truncated(project: Project):
        environment = Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        for index in range(3):
            Release.objects.create(
                environment=environment,
                branch="main",
                commit=f"limit{index}deadbeef",
            )

        response = admin_client.get(reverse("releases:index"), {"limit": "2"})
        html = response.content.decode("utf-8")
        expect(response.status_code) == 200
        expect(response.context["history_limit"]) == 2
        expect(response.context["release_graph_truncated"]) == True
        expect(len(response.context["release_graph"]["nodes"])) == 2
        expect(html).contains("releases-graph-truncated")

        exact = admin_client.get(reverse("releases:index"), {"limit": "3"})
        expect(exact.context["release_graph_truncated"]) == False
        expect(len(exact.context["release_graph"]["nodes"])) == 3
        expect(exact.content.decode("utf-8")).excludes("releases-graph-truncated")

    @pytest.mark.django_db
    def it_includes_review_releases_when_requested(project: Project):
        placeholder = Environment.objects.create(
            project=project,
            name=Type.REVIEW,
            url="https://app-{slug}.example.com",
        )
        concrete = Environment.objects.create(
            project=project,
            name=Type.REVIEW,
            url="https://app-pr-1.example.com",
        )
        Release.objects.create(
            environment=concrete, branch="feature", commit="reviewdeadbeef"
        )

        hidden = admin_client.get(reverse("releases:index"))
        expect(hidden.status_code) == 200
        expect(hidden.context["show_review"]) == False
        expect(hidden.context["release_graph"]["nodes"]) == []
        # Placeholder review templates always appear in Environment Dependencies.
        expect(len(hidden.context["environment_graph"]["nodes"])) == 1
        expect(hidden.context["environment_graph"]["nodes"][0]["id"]) == str(
            placeholder.pk
        )
        expect(
            [column["id"] for column in hidden.context["release_graph"]["columns"]]
        ) == ["deployed"]
        expect(
            [column["id"] for column in hidden.context["environment_graph"]["columns"]]
        ) == [
            "review",
            "staging",
            "production",
        ]

        shown = admin_client.get(reverse("releases:index"), {"review": "true"})
        shown_html = shown.content.decode("utf-8")
        expect(shown.status_code) == 200
        expect(shown.context["show_review"]) == True
        expect(shown_html).contains("reviewdeadbeef")
        expect(
            [column["id"] for column in shown.context["release_graph"]["columns"]]
        ) == [
            "review",
            "deployed",
        ]
        expect(
            [node["subtitle"] for node in shown.context["environment_graph"]["nodes"]]
        ) == ["https://app-{slug}.example.com"]
        expect(
            [node["subtitle"] for node in shown.context["release_graph"]["nodes"]]
        ) == ["https://app-pr-1.example.com"]
        expect(len(shown.context["environment_graph"]["nodes"])) == 1
        expect(len(shown.context["release_graph"]["nodes"])) == 1

    @pytest.mark.django_db
    def it_scopes_to_organization_and_excludes_local(project: Project):
        other = Project.objects.create(repository="https://github.com/other/repo")
        Environment.objects.create(
            project=other, name=Type.PRODUCTION, url="https://other.example.com"
        )
        Environment.objects.create(
            project=project, name=Type.STAGING, url="https://staging.example.com"
        )
        local = Environment.objects.create(
            project=project, name=Type.LOCAL, url="http://localhost:3000"
        )
        Release.objects.create(environment=local, branch="", commit="localonlydeadbeef")

        response = admin_client.get(reverse("releases:index"))
        html = response.content.decode("utf-8")
        expect(response.status_code) == 200
        expect(html).contains("Staging")
        expect(html).excludes("other.example.com")
        expect(html).excludes("localhost:3000")
        expect(html).excludes("localonly")
        expect(html).excludes('"id": "local"')

    @pytest.mark.django_db
    def it_shows_empty_states_without_data():
        response = admin_client.get(reverse("releases:index"))
        html = response.content.decode("utf-8")
        expect(response.status_code) == 200
        expect(html).contains("No environments found")
        expect(html).contains("No releases found")
        expect(html).contains("show-review-releases")
        expect(html).excludes("environment-graph-data")
        expect(html).excludes("release-graph-data")
