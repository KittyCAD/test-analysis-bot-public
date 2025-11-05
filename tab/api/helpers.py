import re
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.cache import cache

import log
from github import Auth, Github, GithubException, GithubIntegration

from tab.core.models import Organization
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Suite, Test
from tab.projects.types import Health

from .constants import TESTS_CACHE_KEY, TESTS_CACHE_TIMEOUT


def parse_junit_xml(
    content: str,
    project: Project,
    suite: Suite,
    branch: str,
    commit: str,
    metadata: dict,
    deferred: bool = False,
) -> list[Result]:
    results = []

    xml = ET.fromstring(content)
    root_name = xml.get("name", "")

    tests_data_to_create: list[dict] = []
    results_data_to_create: list[dict] = []

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
            name = re.sub(r"(\S)\[", r"\1 [", name)  # pytest parametrized tests

            if deferred:
                # Prepare bulk data
                test_data = {
                    "project": project,
                    "name": name,
                    "suite": suite,
                    "original_branch": branch,
                    "original_commit": commit,
                    "original_metadata": metadata,
                }
                result_data = {
                    "test_name": name,
                    "suite": suite,
                    "branch": branch,
                    "commit": commit,
                    "status": status,
                    "duration": duration,
                    "message": message,
                    "metadata": metadata,
                }
                tests_data_to_create.append(test_data)
                results_data_to_create.append(result_data)
            else:
                # Create or update test
                test, created = Test.objects.get_or_create(
                    project=project,
                    name=name,
                    defaults=dict(
                        suite=suite,
                        original_branch=branch,
                        original_commit=commit,
                        original_metadata=metadata,
                    ),
                )
                if test.suite != suite or not test.original_branch:
                    test.suite = suite
                    test.original_branch = test.original_branch or branch
                    test.original_commit = test.original_commit or commit
                    test.original_metadata = test.original_metadata or metadata
                    test.save()
                    log.info(f"Updated test: {test}")
                elif created:
                    log.info(f"Created test: {test}")
                else:
                    log.info(f"Found test: {test}")

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
                log.info(f"Created result: {result}")
                results.append(result)

    if deferred:
        # Bulk operations
        existing_tests: dict[str, Test] = {}
        for test in Test.objects.filter(
            project=project, name__in=[t["name"] for t in tests_data_to_create]
        ):
            existing_tests[test.name] = test
        log.info(f"Found tests: {len(existing_tests)}")

        # Bulk update tests
        tests_to_update: list[Test] = []
        for test in existing_tests.values():
            if test.suite != suite or not test.original_branch:
                test.suite = suite
                test.original_branch = test.original_branch or branch
                test.original_commit = test.original_commit or commit
                test.original_metadata = test.original_metadata or metadata
                tests_to_update.append(test)

        if tests_to_update:
            Test.objects.bulk_update(
                tests_to_update,
                ["suite", "original_branch", "original_commit", "original_metadata"],
            )
            log.info(f"Updated tests: {len(tests_to_update)}")

        # Bulk create tests
        tests_to_create: list[Test] = []
        for test_data in tests_data_to_create:
            if test_data["name"] not in existing_tests:
                tests_to_create.append(Test(**test_data))
            else:
                test = existing_tests[test_data["name"]]  # type: ignore[index]
                tests_to_update.append(test)
        if tests_to_create:
            Test.objects.bulk_create(tests_to_create)
            for test in tests_to_create:
                existing_tests[test.name] = test
            log.info(f"Created tests: {len(tests_to_create)}")

        # Bulk create results
        results_to_create: list[Result] = []
        for result_data_item in results_data_to_create:
            test = existing_tests[result_data_item["test_name"]]
            result = Result(
                test=test,
                suite=result_data_item["suite"],
                branch=result_data_item["branch"],
                commit=result_data_item["commit"],
                status=result_data_item["status"],
                duration=result_data_item["duration"],
                message=result_data_item["message"],
                metadata=result_data_item["metadata"],
            )
            result.normalize()
            results_to_create.append(result)

        if results_to_create:
            Result.objects.bulk_create(results_to_create)
            results.extend(results_to_create)
            log.info(f"Created results: {len(results_to_create)}")

        # Store IDs to call save() logic via cron since bulk_create() skips this
        test_ids = set(result.test.id for result in results)
        if existing_test_ids := cache.get(TESTS_CACHE_KEY):
            test_ids |= set(existing_test_ids)
        cache.set(TESTS_CACHE_KEY, test_ids, timeout=TESTS_CACHE_TIMEOUT)

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
        data = getattr(e, "data", {})
        log.error(f"Unable to update status for {project.path} @ {sha[:7]}: {data}")
        return

    try:
        commit.create_status(
            state=health.state,
            target_url=f"{settings.BASE_URL}/projects/{project.path}/results?branch={branch}&show=fails",
            description=health.description,
            context="Test Analysis Bot",
        )
        log.info(f"Updated status for {project.path} @ {sha[:7]}: {health.state}")
    except GithubException as e:
        data = getattr(e, "data", {})
        if "maximum number of statuses" in str(data):
            log.warning(
                f"Unable to update status for {project.path} @ {sha[:7]}: {data}"
            )
        else:
            raise e from None
