import re

RESULT_SAMPLE_COUNT = 100

ANSI_ESCAPE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")


def get_default_branches():
    return ["main"]
