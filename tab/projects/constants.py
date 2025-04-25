import re

SAMPLE_COUNT = 100  # TODO: Consider making configurable per project

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")


def get_default_branches():
    return ["main"]
