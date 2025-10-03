from django.db import models


class Type(models.TextChoices):
    LOCAL = "local", "Local"
    PREVIEW = "preview", "Preview"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"
