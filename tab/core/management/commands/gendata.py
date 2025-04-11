from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from tab.core.models import Organization


class Command(BaseCommand):
    help = "Create a default superuser if one does not exist"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin", email="user@example.com", password="password"
            )
            self.stdout.write(self.style.SUCCESS("Default superuser created"))
        else:
            self.stdout.write(self.style.WARNING("Default superuser already exists"))

        organization, created = Organization.objects.get_or_create(
            name="Zoo",
            email_domain="zoo.dev",
            repository_index="https://github.com/KittyCAD",
            key="localhost",
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Default organization created"))
        else:
            self.stdout.write(self.style.WARNING("Default organization already exists"))
