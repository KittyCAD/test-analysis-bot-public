import re

ALL_BRANCHES = "all"

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")


def get_default_branches():
    return ["main"]
