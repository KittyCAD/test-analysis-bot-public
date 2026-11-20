import re
from datetime import timedelta

DEFAULT_SUITE = "default"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
PYTEST_DIFF_PLUS = re.compile(r"^(E\s+)(\s*\+.*)$")
PYTEST_DIFF_MINUS = re.compile(r"^(E\s+)(\s*\-.*)$")
UNIFIED_DIFF_PLUS = re.compile(r"^(\s*)(\+.*)$")
UNIFIED_DIFF_MINUS = re.compile(r"^(\s*)(-.*)$")
PYTEST_APPROX_OBTAINED = re.compile(r"^(E\s+)(Obtained:.*)$")
PYTEST_APPROX_EXPECTED = re.compile(r"^(E\s+)(Expected:.*)$")
CHECKOUT_COMMAND = (
    "git fetch origin && git checkout {branch} && git reset --hard origin/{branch}"
)

# Matches a format placeholder, e.g. the {test.name} in 'pytest -k "{test.name}"'
INTERPOLATION = re.compile(r"\{[^}]*\}")

# Matches one command argument, keeping quoted values together
ARGUMENT = re.compile(r"""(?:[^\s"']|"[^"]*"|'[^']*')+""")

# Matches a trailing /<name>/<kind>/<number> path, e.g. modeling-app/pull/13881
TRACKER_REFERENCE = re.compile(r"/(?P<label>[^/]+/[^/]+/\d+)/?$")

PENDING_THRESHOLD = timedelta(minutes=15)  # minimum duration before reporting failures
EXPIRED_THRESHOLD = PENDING_THRESHOLD * 2  # maximum duration to expect suite runs
FAILURE_RATE_EPSILON = 0.001  # small value to keep tests disabled for a bit longer
RESTORATION_THRESHOLD = timedelta(days=3)  # minimum duration to keep tests disabled

DURATION_CACHE_KEY = "projects:duration"
DURATION_CACHE_TIMEOUT = timedelta(minutes=1).total_seconds()

# Shared hover tips for suite setup / tests / teardown (results box + charts)
SETUP_DURATION_TIP = (
    "Shared time spent on cache downloads, installs, and builds before tests run"
)
TESTS_DURATION_TIP = (
    "Total duration from setup completion to the final test reporting results"
)
TEARDOWN_DURATION_TIP = (
    "Shared time spent on reports, archives, and cleanup after tests finish"
)

# Shared chart colors for suite setup / tests / teardown (history + metrics)
SETUP_DURATION_COLOR = "#6f42c1"
SETUP_DURATION_FILL = "rgba(111, 66, 193, 0.35)"
TESTS_DURATION_COLOR = "#0dcaf0"
TESTS_DURATION_FILL = "rgba(13, 202, 240, 0.35)"
TEARDOWN_DURATION_COLOR = "#fd7e14"
TEARDOWN_DURATION_FILL = "rgba(253, 126, 20, 0.35)"

# Legend / run order. History chart may restack Setup+Teardown under Tests for fills.
SUITE_DURATION_SERIES = (
    {
        "label": "Setup",
        "field": "setup_duration",
        "color": SETUP_DURATION_COLOR,
        "fill": SETUP_DURATION_FILL,
        "tip": SETUP_DURATION_TIP,
    },
    {
        "label": "Tests",
        "field": "tests_duration",
        "color": TESTS_DURATION_COLOR,
        "fill": TESTS_DURATION_FILL,
        "tip": TESTS_DURATION_TIP,
    },
    {
        "label": "Teardown",
        "field": "teardown_duration",
        "color": TEARDOWN_DURATION_COLOR,
        "fill": TEARDOWN_DURATION_FILL,
        "tip": TEARDOWN_DURATION_TIP,
    },
)


ACTIVE_BRANCHES_CACHE_KEY = "projects:active_branches"
ACTIVE_BRANCHES_CACHE_TIMEOUT = int(timedelta(hours=1).total_seconds())


def get_default_branches():
    return ["main"]
