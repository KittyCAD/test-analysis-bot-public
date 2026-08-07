from django.db import models
from django.db.models import Case, IntegerField, Value, When


class Type(models.TextChoices):
    LOCAL = "local", "Local"
    REVIEW = "review", "Review"
    STAGING = "staging", "Staging"
    PRODUCTION = "production", "Production"

    @property
    def color(self) -> str:
        match self:
            case self.LOCAL:
                return "#6c757d"
            case self.REVIEW:
                return "#fd7e14"
            case self.STAGING:
                return "#0d6efd"
            case self.PRODUCTION:
                return "#198754"
            case _:
                return "#6c757d"

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
