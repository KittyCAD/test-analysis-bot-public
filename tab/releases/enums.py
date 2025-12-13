from django.db import models
from django.db.models import Case, IntegerField, Value, When


class Type(models.TextChoices):
    LOCAL = "local", "Local"
    REVIEW = "review", "Review"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"

    @classmethod
    def order_expression(cls):
        """Returns a Case expression for ordering by enum definition order."""
        choices = list(cls)
        return Case(
            *[
                When(name=choice.value, then=Value(i))  # type: ignore[attr-defined]
                for i, choice in enumerate(choices, start=1)
            ],
            output_field=IntegerField(),
        )
