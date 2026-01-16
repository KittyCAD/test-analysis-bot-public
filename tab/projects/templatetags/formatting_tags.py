from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from tab.metrics.constants import DELTA_THRESHOLD

from ..helpers import humanize_duration
from ..models import Test
from ..tables import color

register = template.Library()


@register.simple_tag
def colorize(test: Test, field_name: str) -> str:
    """Add color and trend indicators to test attributes."""
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


@register.filter
def duration(value):
    """Format durations to show minutes and seconds."""
    return humanize_duration(value)


@register.filter
def highlight(value):
    """Highlight diff lines: green for additions (+), red for deletions (-)."""
    if not value:
        return value

    lines = value.splitlines(keepends=True)
    result_lines = []

    for line in lines:
        has_newline = line.endswith("\n")
        line_content = line.rstrip("\n\r")

        if line_content.startswith("+"):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-success">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
        elif line_content.startswith("-"):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-danger">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
        else:
            result_lines.append(escape(line))

    return mark_safe("".join(result_lines))
