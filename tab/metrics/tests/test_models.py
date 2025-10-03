import pytest

from tab.core.models import Organization
from tab.projects.models import Project, Suite, Test

from ..models import Alert, History, Subscription, Team


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
        return Alert.objects.create(history=history)

    def describe_teams():
        @pytest.mark.django_db
        def it_sorts_by_primary(expect, organization: Organization, alert: Alert):
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
