from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

import pytest

from tab.core.models import Organization
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Suite, Test

from ..models import Alert, History, Subscription, Team


def describe_history():

    def describe_evaluate():
        def it_skips_alert_if_the_test_is_disabled(expect):
            test = Test(enabled=False)
            history = History(test=test)
            expect(history.evaluate()) == False

        @pytest.mark.django_db
        def it_alerts_when_above_the_threshold(expect):

            project = Project.objects.create(repository="https://github.com/foo/bar")
            test = Test.objects.create(project=project, name="my-test")
            test.last_result = Result.objects.create(
                test=test, branch="main", status=Status.PASSED
            )
            assert test.enabled == True

            # Create the initial record
            history: History = History.objects.create(
                test=test, failure_rate=0, block_rate=0, average_duration=0
            )
            history.timestamp = timezone.now() - timedelta(days=1)
            history.save()
            cache.clear()

            # Increase the failure rate slightly
            test.failure_rate = 0.01
            history = History.objects.create(
                test=test, failure_rate=0.01, block_rate=0, average_duration=0
            )
            expect(history.evaluate()) == False

            # Exceed the failure rate threshold: flat trend line
            test.failure_rate = 0.40
            test.block_rate = 0.01
            history = History.objects.create(
                test=test,
                failure_rate=test.failure_rate,
                block_rate=-1,
                average_duration=-1,
            )
            test.failure_rate = 0.40
            history = History.objects.create(
                test=test,
                failure_rate=test.failure_rate,
                block_rate=-1,
                average_duration=-1,
            )
            expect(history.evaluate()) == False

            # Exceed the failure rate threshold: upward trend line but non-blocking
            test.failure_rate = 0.35
            test.block_rate = 0
            history = History.objects.create(
                test=test,
                failure_rate=0.35,
                block_rate=-1,
                average_duration=-1,
            )
            expect(history.evaluate()) == False

            # Exceed the failure rate threshold: upward trend line and blocking
            test.failure_rate = 0.36
            test.block_rate = 0.01
            history = History.objects.create(
                test=test,
                failure_rate=0.35,
                block_rate=-1,
                average_duration=-1,
            )
            expect(history.evaluate()) == True


def describe_alert():

    @pytest.fixture
    def organization():
        return Organization.objects.create(name="my-slack")

    @pytest.fixture
    def alert():
        project = Project.objects.create(
            repository="https://github.com/my-user/my-project"
        )
        suite = Suite.objects.create(project=project, name="my-suite")
        test = Test.objects.create(project=project, suite=suite, name="my-test")
        history = History.objects.create(
            test=test, failure_rate=-1, block_rate=-1, average_duration=-1
        )
        return Alert.objects.create(test=test, history=history)

    def describe_teams():
        @pytest.mark.django_db
        def it_sorts_by_primary(expect, organization: Organization, alert: Alert):
            assert alert.history and alert.history.test
            project = alert.history.test.project
            t1 = Team.objects.create(
                organization=organization, slack_channel_name="#primary"
            )
            s1 = Subscription.objects.create(team=t1, project=project, primary=True)
            t2 = Team.objects.create(
                organization=organization, slack_channel_name="#secondary"
            )
            s2 = Subscription.objects.create(team=t2, project=project, primary=False)

            expect(alert.subscriptions) == [s1, s2]

        @pytest.mark.django_db
        def it_matches_by_suite_and_test(
            expect, organization: Organization, alert: Alert
        ):
            assert alert.history and alert.history.test
            project = alert.history.test.project
            suite = alert.history.test.suite
            team = Team.objects.create(
                organization=organization, slack_channel_name="#foobar"
            )
            s1 = Subscription.objects.create(team=team, project=project, suite=suite)
            s2 = Subscription.objects.create(team=team, project=project, test="my-test")
            s3 = Subscription.objects.create(
                team=team, project=project, suite=suite, test="xyz|.*test"
            )
            s4 = Subscription.objects.create(team=team, project=project, test="other")
            s5 = Subscription.objects.create(
                team=team, project=project, suite=suite, test="other"
            )
            s6 = Subscription.objects.create(
                team=team,
                project=project,
                suite=Suite.objects.create(project=project, name="other"),
            )

            expect(alert.subscriptions) == [s1, s3, s2]
