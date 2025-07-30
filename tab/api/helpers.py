import xml.etree.ElementTree as ET

from django.conf import settings

import log
from github import Auth, Github, GithubException, GithubIntegration

from tab.core.models import Organization
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Suite, Test
from tab.projects.types import Health


def parse_junit_xml(
    content: str,
    project: Project,
    suite: Suite,
    branch: str,
    commit: str,
    metadata: dict,
) -> list[Result]:
    results = []

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
            system = testcase.find("system-err")

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

            if system is not None:
                message = message or system.text

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
                    suite=suite,
                    original_branch=branch,
                    original_commit=commit,
                    metadata=metadata,
                ),
            )
            if not all([test.suite, test.original_branch, test.original_commit]):
                test.suite = test.suite or suite
                test.original_branch = test.original_branch or branch
                test.original_commit = test.original_commit or commit
                test.metadata = test.metadata or metadata
                test.save()

            # Create result
            result = Result.objects.create(
                test=test,
                suite=suite,
                branch=branch,
                commit=commit,
                status=status,
                duration=duration,
                message=message,
                metadata=metadata,
            )
            results.append(result)

    return results


def update_status(
    organization: Organization,
    project: Project,
    sha: str,
    branch: str,
    health: Health,
):
    assert "github.com" in project.repository, "Only GitHub is supported for now"

    if organization.github_app_id and organization.github_app_private_key:
        log.debug("Authenticating with GitHub App")
        auth = Auth.AppAuth(
            organization.github_app_id, organization.github_app_private_key
        )
        integration = GithubIntegration(auth=auth)
        installation = integration.get_org_installation(
            organization.repository_index.removeprefix("https://github.com/")
        )
        github = installation.get_github_for_installation()
    elif organization.repository_token:
        log.debug("Authenticating with repository token")
        github = Github(organization.repository_token)
    else:
        log.warning(f"{organization} has no repository token")
        return

    try:
        repo = github.get_repo(project.path)
        commit = repo.get_commit(sha)
    except GithubException as e:
        message = str(e)
        log.error(f"Unable to update status for {project.path} @ {sha[:7]}: {message}")
        return 404, {"detail": message}
    commit.create_status(
        state=health.state,
        target_url=f"{settings.BASE_URL}/projects/{project.path}/results?branch={branch}&show=fails",
        description=health.description,
        context="Test Analysis Bot",
    )
    log.info(f"Updated status for {project.path} @ {sha[:7]}: {health.state}")
