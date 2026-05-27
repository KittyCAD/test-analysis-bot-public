import pytest

from tab.projects.models import Project, Result, Suite, Test
from tab.releases.enums import Type
from tab.releases.models import Environment, Release


def describe_process():

    @pytest.fixture
    def project():
        return Project.objects.create(
            repository="https://github.com/my-org/modeling-app",
            default_branches=["main"],
        )

    @pytest.fixture
    def placeholder_environment(project):
        return Environment.objects.create(
            project=project,
            name=Type.REVIEW,
            url="https://modeling-{slug}.vercel.dev.zoo.dev",
        )

    @pytest.fixture
    def result(project):
        suite = Suite.objects.create(project=project, name="unit")
        test = Test.objects.create(project=project, name="my test", suite=suite)
        return Result.objects.create(
            test=test,
            suite=suite,
            branch="feature/my-branch",
            commit="abc123",
            status="passed",
        )

    @pytest.mark.django_db
    def it_reuses_release_when_concrete_url_follows_placeholder(
        expect, project, placeholder_environment, result
    ):
        Environment.objects.process(project, None, [result])

        result2 = Result.objects.create(
            test=result.test,
            suite=result.suite,
            branch=result.branch,
            commit=result.commit,
            status="passed",
        )
        Environment.objects.process(
            project,
            "https://modeling-foobar.vercel.dev.zoo.dev",
            [result2],
        )

        releases = Release.objects.filter(branch=result.branch, commit=result.commit)
        expect(releases.count()) == 1
        release: Release = releases.first()  # type: ignore[assignment]
        expect(release.results) == 2
        expect(release.environment.url) == (
            "https://modeling-foobar.vercel.dev.zoo.dev"
        )
        expect(release.environment_id) != placeholder_environment.id
        expect(Environment.objects.filter(name=Type.REVIEW).count()) == 2

    @pytest.mark.django_db
    def it_creates_release_on_concrete_url_when_none_exists_yet(
        expect, project, result
    ):
        Environment.objects.process(
            project,
            "https://modeling-foobar.vercel.dev.zoo.dev",
            [result],
        )

        release = Release.objects.get(branch=result.branch, commit=result.commit)
        expect(release.results) == 1
        expect(release.environment.url) == (
            "https://modeling-foobar.vercel.dev.zoo.dev"
        )
