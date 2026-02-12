import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

import log

from tab.core.models import Organization
from tab.metrics.models import History, Team
from tab.projects.enums import Platform, Status, Target
from tab.projects.models import Project, Result, Test


class Command(BaseCommand):
    help = "Create sample organization, project, and metrics"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        for action in parser._actions:
            if "--verbosity" in getattr(action, "option_strings", []):
                action.default = 2  # INFO and above by default
                break

    def handle(self, *args, **options):
        log.reset()
        log.init(verbosity=options["verbosity"])
        self.create_default_user()
        self.create_default_organization()
        self.create_default_team()
        self.generate_sample_data()

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

    def generate_sample_data(self):
        for test in Test.objects.filter(name="sample test"):
            test.save()  # ensure sample tests are enabled

        project, created = Project.objects.get_or_create(
            repository="https://github.com/KittyCAD/sample-project"
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created sample project"))
        else:
            self.stdout.write(self.style.WARNING("Sample project already exists"))

        for test in project.tests.all():
            test.save()  # ensure last_result and enabled are updated

        test, created = Test.objects.get_or_create(
            project=project, name="sample test", original_branch="main"
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created sample test"))
        else:
            self.stdout.write(self.style.WARNING(f"Sample test already exists"))
            test.history.all().delete()

        test.results.all().delete()

        days = 8
        num_results = 500
        end = timezone.now()
        start = end - timedelta(days=days)

        self._generate_results(test, num_results, start, end)
        self._generate_history(test, days)

    def _generate_history(self, test, days):
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
        self.stdout.write(self.style.SUCCESS("Generated history metrics"))

    def _generate_results(self, test, num_results, start, end):
        statuses = [Status.PASSED, Status.FAILED]
        targets = [None, Target.WEB, Target.DESKTOP]
        platforms = [None, Platform.MACOS, Platform.WINDOWS, Platform.LINUX]
        sample_messages = [
            "",
            "AssertionError: expected 42",
            "Timeout 5000ms exceeded",
            "Connection refused to localhost:5432",
            "Element not found: .submit-btn",
            "ValueError: invalid literal for int()",
            "All assertions passed",
            "Test completed successfully",
        ]
        for i in range(num_results):
            fraction = (i + 0.5) / num_results
            created_at = start + (end - start) * fraction
            result = Result.objects.create(
                test=test,
                branch="main",
                commit=f"sample{i:05x}",
                status=random.choice(statuses),
                duration=round(random.uniform(15.0, 60.0), 2),
                final=True,
                message=random.choice(sample_messages),
                target=random.choice(targets),
                platform=random.choice(platforms),
            )
            result.created_at = created_at
            result.save(update_fields=["created_at"])
            if (i + 1) % 10 == 0:
                self.stdout.write(f"Generated {i + 1}/{num_results} results")
        self.stdout.write(self.style.SUCCESS("Generated test results"))
