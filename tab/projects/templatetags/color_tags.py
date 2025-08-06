from django import template

from tab.metrics.constants import DELTA_THRESHOLD

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
    tooltip = icon = ""

    if delta := getattr(test, f"{field_name}_delta", None):

        if delta >= DELTA_THRESHOLD:
            icon = "angles-up"
        elif delta >= DELTA_THRESHOLD / 2:
            icon = "angle-up"
        elif delta <= -DELTA_THRESHOLD:
            icon = "angles-down"
        elif delta <= -DELTA_THRESHOLD / 2:
            icon = "angle-down"

        if delta > 0:
            tooltip = f"+{delta:.1%} today"
        elif delta < 0:
            tooltip = f"{delta:.1%} today"

    return color(text, value, lower_threshold, upper_threshold, icon, tooltip)
