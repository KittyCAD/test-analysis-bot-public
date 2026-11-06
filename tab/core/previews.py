from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from PIL import Image, ImageDraw, ImageFont

from tab.metrics.constants import DELTA_THRESHOLD
from tab.projects.enums import Status
from tab.projects.models import Project, Result, Suite, Test

SIZE = 512
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
LOGO_PATH = Path(settings.BASE_DIR) / "static/favicon/web-app-manifest-512x512.png"
RECENT_RESULT_COUNT = 20
RESULT_COLUMNS = 10

# Bootstrap 5
SUCCESS = (25, 135, 84)  # #198754
DANGER = (220, 53, 69)  # #dc3545
WARNING = (255, 193, 7)  # #ffc107
INFO = (13, 202, 240)  # #0dcaf0
SECONDARY = (108, 117, 125)  # #6c757d
BACKGROUND = (248, 249, 250)  # #f8f9fa
MUTED = (108, 117, 125)  # #6c757d
INK = (33, 37, 41)  # #212529
WHITE = (255, 255, 255)
EMPTY_SQUARE = (222, 226, 230)  # #dee2e6

STATUS_COLORS = {
    "success": SUCCESS,
    "danger": DANGER,
    "warning": WARNING,
    "info": INFO,
    "secondary": SECONDARY,
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / name), size=size)


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    if plural is None:
        plural = singular + "s"
    return singular if count == 1 else plural


def _failure_rate_threshold(test: Test) -> float:
    if test.suite_id:
        assert test.suite is not None
        return test.suite.failure_rate_lower_threshold
    return Suite._meta.get_field("failure_rate_lower_threshold").default


def is_unhealthy(test: Test) -> bool:
    """True when the failure rate is above the suite's acceptable floor."""
    if test.failure_rate < 0:
        return False
    return test.failure_rate >= _failure_rate_threshold(test)


def _status_color(status: str) -> tuple[int, int, int]:
    try:
        return STATUS_COLORS[Status(status).color]
    except ValueError:
        return SECONDARY


def _recent_statuses_for_test(test: Test) -> list[str]:
    statuses = list(
        test.results.filter(branch__in=test.significant_branches)
        .order_by("-created_at")
        .values_list("status", flat=True)[:RECENT_RESULT_COUNT]
    )
    statuses.reverse()
    return statuses


def _recent_statuses_for_project(
    project: Project, *, suite: Suite | None = None
) -> list[str]:
    queryset = Result.objects.filter(
        test__project=project,
        branch__in=project.default_branches,
    )
    if suite is not None:
        queryset = queryset.filter(test__suite=suite)
    statuses = list(
        queryset.order_by("-created_at").values_list("status", flat=True)[
            :RECENT_RESULT_COUNT
        ]
    )
    statuses.reverse()
    return statuses


def _least_reliable_count(project: Project) -> int:
    week_ago = timezone.now() - timedelta(days=7)
    least_reliable = (
        Q(failure_rate__gt=0.25, block_rate__gt=0)
        | Q(block_rate__gt=0.05, failure_rate__gt=0.20)
        | Q(failure_rate__gt=0.33)
        | Q(average_duration__gt=90)
    )
    return (
        project.tests.filter(
            least_reliable,
            created_at__lte=week_ago,
            last_result__isnull=False,
            last_result__created_at__gte=week_ago,
            disabled_at__isnull=True,
        )
        .exclude(last_result__status=Status.DISABLED)
        .count()
    )


def _draw_result_squares(
    draw: ImageDraw.ImageDraw,
    statuses: list[str],
    box: tuple[int, int, int, int],
):
    left, top, right, bottom = box
    columns = RESULT_COLUMNS
    rows = max(1, (RECENT_RESULT_COUNT + columns - 1) // columns)
    gap = 6
    usable_w = right - left - gap * (columns - 1)
    usable_h = bottom - top - gap * (rows - 1)
    square = min(usable_w // columns, usable_h // rows)
    grid_w = columns * square + (columns - 1) * gap
    grid_h = rows * square + (rows - 1) * gap
    origin_x = left + (right - left - grid_w) // 2
    origin_y = top + (bottom - top - grid_h) // 2

    padded: list[str | None] = [None] * (RECENT_RESULT_COUNT - len(statuses)) + list(
        statuses
    )

    for index, status in enumerate(padded):
        row, col = divmod(index, columns)
        x = origin_x + col * (square + gap)
        y = origin_y + row * (square + gap)
        color = EMPTY_SQUARE if status is None else _status_color(status)
        draw.rounded_rectangle(
            (x, y, x + square, y + square),
            radius=4,
            fill=color,
        )


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int | None = None,
) -> tuple[str, int, int]:
    """Return display text plus width/height for layout measurements."""
    display = text
    if max_width is not None:
        while display and draw.textbbox((0, 0), display, font=font)[2] > max_width:
            if len(display) <= 1:
                break
            display = display[:-2] + "…"
    bbox = draw.textbbox((0, 0), display, font=font)
    return display, int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    image_width: int = SIZE,
    max_width: int | None = None,
) -> int:
    """Draw centered text; returns the y position just below the text."""
    display, text_width, text_height = _fit_text(draw, text, font, max_width)
    draw.text(((image_width - text_width) / 2, y), display, font=font, fill=fill)
    return y + text_height + 8


def _save_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


TILES_BOTTOM = 40  # padding from bottom edge for status tiles
TILES_HEIGHT = 110


def _tiles_box() -> tuple[int, int, int, int]:
    """Fixed bottom band for status tiles."""
    bottom = SIZE - TILES_BOTTOM
    top = bottom - TILES_HEIGHT
    return (40, top, SIZE - 40, bottom)


def _render_stat_card(
    *,
    primary: str,
    primary_color: tuple[int, int, int],
    label: str,
    secondary: str | None = None,
    secondary_color: tuple[int, int, int] | None = None,
    statuses: list[str] | None = None,
    primary_size: int = 120,
) -> bytes:
    image = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    draw = ImageDraw.Draw(image)

    rate_font = _font("DejaVuSans-Bold.ttf", primary_size)
    label_font = _font("DejaVuSans.ttf", 36)
    secondary_font = _font("DejaVuSans-Bold.ttf", 34)
    max_width = SIZE - 48

    # gap_after is the full space after each line (number → label needs more air)
    lines: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int], int]] = [
        (primary, rate_font, primary_color, 72),
        (label, label_font, MUTED, 16 if secondary else 0),
    ]
    if secondary:
        lines.append((secondary, secondary_font, secondary_color or MUTED, 0))

    total_height = 0
    measured: list[tuple[str, ImageFont.FreeTypeFont, tuple, int, int]] = []
    for index, (text, font, color, gap_after) in enumerate(lines):
        display, width, height = _fit_text(draw, text, font, max_width)
        measured.append((display, font, color, width, height))
        total_height += height
        if index < len(lines) - 1:
            total_height += gap_after

    # Text centered in the area above status tiles (or full canvas if none)
    content_bottom = _tiles_box()[1] - 24 if statuses is not None else SIZE
    y = max(40, (content_bottom - total_height) // 2)
    for index, (display, font, color, width, height) in enumerate(measured):
        draw.text(((SIZE - width) / 2, y), display, font=font, fill=color)
        y += height
        if index < len(measured) - 1:
            y += lines[index][3]

    if statuses is not None:
        _draw_result_squares(draw, statuses, _tiles_box())

    return _save_png(image)


def render_logo_preview_png() -> bytes:
    """Fallback Slack preview using the app logo."""
    logo = Image.open(LOGO_PATH).convert("RGBA")
    if logo.size != (SIZE, SIZE):
        logo = logo.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    image = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    image.paste(logo, (0, 0), logo)
    return _save_png(image)


def render_test_preview_png(test: Test) -> bytes:
    """Slack preview for a test's failure rate and recent results."""
    unhealthy = is_unhealthy(test)
    accent = DANGER if unhealthy else SUCCESS
    delta = test.failure_rate_delta

    if test.failure_rate < 0:
        rate_text = "—"
    else:
        rate_text = f"{test.failure_rate:.0%}"

    secondary = None
    secondary_color = None
    if abs(delta) >= DELTA_THRESHOLD / 2:
        arrow = "▲" if delta > 0 else "▼"
        sign = "+" if delta > 0 else ""
        secondary = f"{arrow} {sign}{delta:.0%} today"
        secondary_color = DANGER if delta > 0 else SUCCESS

    return _render_stat_card(
        primary=rate_text,
        primary_color=accent,
        label="Failure rate",
        secondary=secondary,
        secondary_color=secondary_color,
        statuses=_recent_statuses_for_test(test),
    )


def render_result_preview_png(result: Result) -> bytes:
    """Slack preview for a single test result: centered status badge."""
    status = Status(result.status)
    badge_color = _status_color(result.status)
    image = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    draw = ImageDraw.Draw(image)

    badge_font = _font("DejaVuSans-Bold.ttf", 72)
    label = status.label
    _, label_w, label_h = _fit_text(draw, label, badge_font)

    pad_x, pad_y = 56, 32
    badge_w = label_w + pad_x * 2
    badge_h = label_h + pad_y * 2
    badge_left = (SIZE - badge_w) // 2
    badge_top = (SIZE - badge_h) // 2
    draw.rounded_rectangle(
        (badge_left, badge_top, badge_left + badge_w, badge_top + badge_h),
        radius=24,
        fill=badge_color,
    )
    draw.text(
        (badge_left + pad_x, badge_top + pad_y - 6),
        label,
        font=badge_font,
        fill=WHITE,
    )
    return _save_png(image)


def render_disabled_preview_png(project: Project) -> bytes:
    """Slack preview for a project's disabled-tests page."""
    count = project.tests.disabled().count()
    return _render_stat_card(
        primary=str(count),
        primary_color=INFO if count else SUCCESS,
        label=_pluralize(count, "Disabled test"),
    )


def render_metrics_preview_png(project: Project) -> bytes:
    """Slack preview for a project's metrics page (least-reliable count)."""
    count = _least_reliable_count(project)
    return _render_stat_card(
        primary=str(count),
        primary_color=DANGER if count else SUCCESS,
        label=_pluralize(count, "Unreliable test"),
    )


def render_suite_preview_png(suite: Suite) -> bytes:
    """Slack preview for a suite's tests page: test count + status squares."""
    test_count = suite.tests.count()
    statuses = _recent_statuses_for_project(suite.project, suite=suite)
    if test_count == 0 and not statuses:
        return render_logo_preview_png()
    return _render_stat_card(
        primary=str(test_count),
        primary_color=INK,
        label=_pluralize(test_count, "Suite test"),
        statuses=statuses,
    )


def render_project_preview_png(project: Project, *, is_org: bool) -> bytes:
    """Slack preview for a project (suite count) or organization (project count)."""
    if is_org:
        org = project.path
        count = Project.objects.filter(repository__contains=f"/{org}/").count()
        if count == 0:
            return render_logo_preview_png()
        return _render_stat_card(
            primary=str(count),
            primary_color=INK,
            label=_pluralize(count, "Project"),
        )

    suite_count = project.suites.count()
    if suite_count == 0 and project.tests.count() == 0:
        return render_logo_preview_png()
    return _render_stat_card(
        primary=str(suite_count),
        primary_color=INK,
        label=_pluralize(suite_count, "Suite"),
    )
