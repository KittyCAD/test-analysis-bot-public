from django.db import models
from django.db.models import Case, IntegerField, Value, When


class Type(models.TextChoices):
    LOCAL = "local", "Local"
    PREVIEW = "preview", "Preview"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"

    @classmethod
    def order_expression(cls):
        """Returns a Case expression for ordering by enum definition order."""
        return Case(
            *[When(name=t.value, then=Value(i)) for i, t in enumerate(cls, start=1)],
            output_field=IntegerField(),
        )
