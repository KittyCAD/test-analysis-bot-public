import re
from datetime import timedelta

ALL_BRANCHES = "all"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")

DEFAULT_SUITE = "default"

PENDING_THRESHOLD = timedelta(minutes=10)


def get_default_branches():
    return ["main"]
