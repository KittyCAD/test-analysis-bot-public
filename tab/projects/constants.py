import re
from datetime import timedelta

ALL_BRANCHES = "all"
DEFAULT_SUITE = "default"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")

PENDING_THRESHOLD = timedelta(minutes=10)  # duration to stop waiting for new results
NEW_FAILURE_THRESHOLD = 0.25  # minimum failure rate to consider failures expected


def get_default_branches():
    return ["main"]
