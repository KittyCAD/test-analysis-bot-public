import re
from datetime import timedelta

ALL_BRANCHES = "all"
DEFAULT_SUITE = "default"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
CHECKOUT_COMMAND = (
    "git fetch origin && git checkout {branch} && git reset --hard origin/{branch}"
)

PENDING_THRESHOLD = timedelta(minutes=15)  # duration to stop waiting for new results
FAILURE_RATE_EPSILON = 0.001  # small value to keep tests disabled for a bit longer


def get_default_branches():
    return ["main"]
