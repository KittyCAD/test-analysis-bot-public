import secrets

from django.db import models


def generate_key() -> str:
    return "".join(secrets.choice("0123456789abcdef") for _ in range(32))


class Organization(models.Model):
    name = models.CharField(max_length=100)
    email_domain = models.CharField(max_length=100, blank=True)
    repository_index = models.URLField(unique=True)
    repository_token = models.CharField(max_length=100, blank=True)
    github_app_id = models.IntegerField(null=True, blank=True)
    github_app_private_key = models.TextField(null=True, blank=True)

    key = models.CharField(max_length=32, unique=True, default=generate_key)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
