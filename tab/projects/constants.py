import re
from datetime import timedelta

ALL_BRANCHES = "all"
DEFAULT_SUITE = "default"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
CHECKOUT_COMMAND = (
    "git fetch origin && git checkout {branch} && git reset --hard origin/{branch}"
)

PENDING_THRESHOLD = timedelta(minutes=10)  # duration to stop waiting for new results
NEW_FAILURE_THRESHOLD = 0.01  # minimum block rate to consider failures expected


def get_default_branches():
    return ["main"]
