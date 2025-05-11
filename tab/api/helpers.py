import xml.etree.ElementTree as ET

from django.conf import settings

import log
from github import Github, GithubException

from tab.core.models import Organization
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Test
from tab.projects.types import Health


def parse_junit_xml(content: str, project: Project, branch: str, commit: str) -> int:
    count = 0
    xml = ET.fromstring(content)
    root_name = xml.get("name", "")
    for testsuite in xml.findall(".//testsuite"):
        suite_name = testsuite.get("name", "")
        for testcase in testsuite.findall("testcase"):
            test_name = testcase.get("name", "")
            class_name = testcase.get("classname", "")
            duration = float(testcase.get("time", 0))

            # Determine test status
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None:
                status = Status.FAILED
                message = failure.text
            elif error is not None:
                status = Status.ERROR
                message = error.text
            elif skipped is not None:
                status = Status.SKIPPED
                message = skipped.text
            else:
                status = Status.PASSED
                message = None

            # Build test name
            name_components = []
            for value in [root_name, suite_name, class_name, test_name]:
                if value and value not in name_components:
                    name_components.append(value)
            name = " › ".join(name_components)

            # Create or update test
            test, _created = Test.objects.get_or_create(
                project=project,
                name=name,
                defaults=dict(
                    original_branch=branch,
                    original_commit=commit,
                ),
            )

            # Create result
            Result.objects.create(
                test=test,
                branch=branch,
                commit=commit,
                status=status,
                duration=duration,
                message=message,
            )
            count += 1

    return count


def update_status(
    organization: Organization,
    project: Project,
    sha: str,
    branch: str,
    health: Health,
):
    assert "github.com" in project.repository, "Only GitHub is supported for now"

    if not organization.repository_token:
        log.warning(f"{organization} has no repository token")
        return

    github = Github(organization.repository_token)
    try:
        repo = github.get_repo(project.path)
        commit = repo.get_commit(sha)
    except GithubException as e:
        return 404, {"detail": str(e)}
    commit.create_status(
        state=health.state,
        target_url=f"{settings.BASE_URL}/projects/{project.path}/results?branch={branch}&show=fails",
        description=health.description,
        context="Test Analysis Bot",
    )
