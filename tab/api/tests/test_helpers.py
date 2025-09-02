from pathlib import Path

from django.core.cache import cache

import pytest

from tab.projects.models import Project, Suite

from ..constants import TESTS_CACHE_KEY
from ..helpers import parse_junit_xml


def describe_parse_junit_xml():

    @pytest.mark.django_db
    def it_recomputes_metrics_from_each_result(expect):
        cache.delete(TESTS_CACHE_KEY)
        path = Path(__file__).parent / "files" / "junit.xml"
        content = path.read_text()
        project = Project.objects.create(repository="https://github.com/foo/bar")
        suite = Suite.objects.create(project=project)

        results = parse_junit_xml(
            content, project, suite, branch="main", commit="abc123", metadata={}
        )

        expect(len(results)) == 25
        expect(results[0].test.failure_rate) >= 0.0
        expect(cache.get(TESTS_CACHE_KEY)) == None

    @pytest.mark.django_db
    def it_caches_test_ids_for_post_processing_when_deferred(expect):
        cache.delete(TESTS_CACHE_KEY)
        path = Path(__file__).parent / "files" / "junit.xml"
        content = path.read_text()
        project = Project.objects.create(repository="https://github.com/foo/bar")
        suite = Suite.objects.create(project=project)

        results = parse_junit_xml(
            content,
            project,
            suite,
            branch="main",
            commit="abc123",
            metadata={},
            deferred=True,
        )

        expect(len(results)) == 25
        expect(results[0].test.failure_rate) == -1  # deferred post-processing
        expect(cache.get(TESTS_CACHE_KEY)) == {result.test.id for result in results}
