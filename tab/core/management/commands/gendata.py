import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tab.core.models import Organization
from tab.metrics.models import History, Subscription, Team
from tab.projects.models import Project, Test


class Command(BaseCommand):
    help = "Create sample organization, project, and metrics"

    def handle(self, *args, **kwargs):
        self.create_default_user()
        self.create_default_organization()
        self.create_default_team()
        self.generate_sample_metrics()

    def create_default_user(self):
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin", email="admin@zoo.dev", password="password"
            )
            self.stdout.write(self.style.SUCCESS("Default superuser created"))
        else:
            self.stdout.write(self.style.WARNING("Default superuser already exists"))

    def create_default_organization(self):
        organization, created = Organization.objects.get_or_create(
            name="Zoo",
            email_domain="zoo.dev",
            repository_index="https://github.com/KittyCAD",
            key="localhost",
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS("Default organization created: %s" % organization)
            )
        else:
            self.stdout.write(self.style.WARNING("Default organization already exists"))

    def create_default_team(self):
        organization = Organization.objects.get(name="Zoo")
        team, created = Team.objects.get_or_create(
            organization=organization,
            slack_channel_name="#test-analysis-bot",
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Default team created: %s" % team))
        else:
            self.stdout.write(self.style.WARNING("Default team already exists"))

    def generate_sample_metrics(self):
        project, created = Project.objects.get_or_create(
            repository="https://github.com/KittyCAD/sample-project"
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created sample project"))
        else:
            self.stdout.write(self.style.WARNING("Sample project already exists"))

        test, created = Test.objects.get_or_create(
            project=project, name="sample test", original_branch="main"
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created sample test"))
        else:
            self.stdout.write(self.style.WARNING(f"Sample test already exists"))
            test.history.all().delete()

        count = 0
        days = 8
        failure_rate = 0.25
        for hour in range(24 * days):
            timestamp = timezone.now() - timedelta(hours=hour)
            delta = random.uniform(0.01, 0.05)
            if hour // 24 % 2 == 0:
                if random.random() < 0.10:
                    failure_rate = max(0.0, failure_rate - delta)
                else:
                    continue
            else:
                if random.random() < 0.20:
                    failure_rate = min(1.0, failure_rate + delta)
                else:
                    continue

            history = History.objects.create(
                test=test,
                failure_rate=failure_rate,
                block_rate=random.uniform(0.0, 0.1),
                average_duration=random.uniform(15.0, 60.0),
            )
            history.timestamp = timestamp
            history.save()
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Generated {count} metrics for past {days} days")
        )
