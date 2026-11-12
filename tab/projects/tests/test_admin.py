from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from tab.projects.models import Project, Result, Status, Test


@pytest.fixture
def project(db):
    return Project.objects.create(repository="https://github.com/foo/bar")


def describe_result_admin(expect, admin_client):
    @pytest.mark.django_db
    def it_avoids_distinct_scans_across_results_for_browser_choices(project: Project):
        test = Test.objects.create(project=project, name="test")
        Result.objects.create(
            test=test,
            branch="main",
            commit="abc123",
            status=Status.PASSED,
            browser="Chrome",
            duration=1.0,
        )

        with CaptureQueriesContext(connection) as queries:
            response = admin_client.get("/admin/projects/result/")

        expect(response.status_code) == 200
        distinct_result_queries = [
            query["sql"]
            for query in queries
            if "DISTINCT" in query["sql"] and "projects_result" in query["sql"]
        ]
        expect(distinct_result_queries) == []
