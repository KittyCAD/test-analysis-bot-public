from datetime import timedelta

from tab.projects.constants import PENDING_THRESHOLD

PLACEHOLDER_CHARACTER = "{"  # indicates a placeholder URL, e.g. "app-{slug}"

CHANGE_HISTORY_LIMIT = 50  # default number of displayed change history items

RESULTS_TIMEOUT = PENDING_THRESHOLD + timedelta(
    minutes=5
)  # maximum time to wait for results
