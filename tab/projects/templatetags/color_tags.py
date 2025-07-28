from django import template

from ..models import Test
from ..tables import color

register = template.Library()


@register.simple_tag
def colorize(test: Test, field_name: str) -> str:
    if not test.suite:
        return getattr(test, f"{field_name}_humanized")

    text = getattr(test, f"{field_name}_humanized")
    value = getattr(test, field_name)
    lower_threshold = getattr(test.suite, f"{field_name}_lower_threshold")
    upper_threshold = getattr(test.suite, f"{field_name}_upper_threshold")

    if delta := getattr(test, f"{field_name}_delta", None):
        tooltip = icon = ""

        if delta > 0:
            tooltip = f"+{delta:.1%} today"
        elif delta < 0:
            tooltip = f"{delta:.1%} today"

        if delta >= 0.1:
            icon = "angles-up"
        elif delta >= 0.05:
            icon = "angle-up"
        elif delta <= -0.1:
            icon = "angles-down"
        elif delta <= -0.05:
            icon = "angle-down"

        if tooltip and icon:
            text += (
                f" <span title='{tooltip}'><i class='fa-solid fa-{icon}'></i></span>"
            )

    return color(text, value, lower_threshold, upper_threshold)
