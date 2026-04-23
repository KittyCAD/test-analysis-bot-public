from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from tab.metrics.constants import DELTA_THRESHOLD

from ..constants import (
    PYTEST_APPROX_EXPECTED,
    PYTEST_APPROX_OBTAINED,
    PYTEST_DIFF_MINUS,
    PYTEST_DIFF_PLUS,
    UNIFIED_DIFF_MINUS,
    UNIFIED_DIFF_PLUS,
)
from ..helpers import humanize_duration, insert_breaks
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

    if value >= 0 and (delta := getattr(test, f"{field_name}_delta", None)):

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
def wrap(value):
    """Insert line-break opportunities for long test names."""
    if value is None:
        return ""
    return mark_safe(insert_breaks(str(value)))


@register.filter
def duration(value):
    """Format durations to show minutes and seconds."""
    return humanize_duration(value)


@register.filter
def highlight(value):
    """Highlight diff lines: green for additions, red for deletions."""
    if not value:
        return value

    lines = value.splitlines(keepends=True)
    result_lines = []
    seen_expected = False
    seen_received = False
    logs_started = False
    in_unified_diff = False

    for line in lines:
        has_newline = line.endswith("\n")
        line_content = line.rstrip("\n\r")
        if line_content.lower().endswith("log:"):
            logs_started = True

        if line_content.lstrip().startswith("Snapshot:"):
            in_unified_diff = False
        elif "@@" in line_content:
            in_unified_diff = True

        # Handle Pytest diffs
        if match := PYTEST_DIFF_PLUS.match(line_content):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-success">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        elif match := PYTEST_DIFF_MINUS.match(line_content):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-danger">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        elif match := PYTEST_APPROX_OBTAINED.match(line_content):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-success">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        elif match := PYTEST_APPROX_EXPECTED.match(line_content):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-danger">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        elif (
            not logs_started
            and in_unified_diff
            and (match := UNIFIED_DIFF_PLUS.match(line_content))
        ):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-success">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        elif (
            not logs_started
            and in_unified_diff
            and (match := UNIFIED_DIFF_MINUS.match(line_content))
        ):
            prefix = escape(match.group(1))
            colored_part = escape(match.group(2))
            result_lines.append(
                f'{prefix}<span class="text-danger">{colored_part}</span>'
            )
            if has_newline:
                result_lines.append("\n")
        # Handle Rust diffs
        elif line_content.startswith("  left:"):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-danger">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
        elif line_content.startswith(" right:"):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-success">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
        # Handle Playwright diffs
        elif line_content.startswith(("+", "Received:", "Received string:")):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-success">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
            if line_content.startswith(("Received:", "Received string:")):
                seen_received = True
        elif (
            line_content.startswith(("-", "Expected:", "Expected substring:"))
            and not logs_started
        ):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-danger">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
            if line_content.startswith(("Expected:", "Expected substring:")):
                seen_expected = True
        elif (
            seen_expected
            and not seen_received
            and line_content.startswith(("Timeout:", "Error:"))
        ):
            escaped = escape(line_content)
            result_lines.append(f'<span class="text-success">{escaped}</span>')
            if has_newline:
                result_lines.append("\n")
        else:
            result_lines.append(escape(line))

    return mark_safe("".join(result_lines))
