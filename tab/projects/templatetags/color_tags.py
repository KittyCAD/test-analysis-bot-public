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

    return color(text, value, lower_threshold, upper_threshold)
