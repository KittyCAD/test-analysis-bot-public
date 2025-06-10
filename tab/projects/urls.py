from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path(
        "",
        views.IndexView.as_view(),
        name="index",
    ),
    path(
        "<path:path>/tests/disabled/regex",
        views.DisabledTestsRegexView.as_view(),
        name="disabled-tests-regex",
    ),
    path(
        "<path:path>/tests/disabled",
        views.DisabledTestsView.as_view(),
        name="disabled-tests",
    ),
    path(
        "<path:path>/tests/<int:test_id>",
        views.TestResultsView.as_view(),
        name="test-results",
    ),
    path(
        "<path:path>/results",
        views.ResultsView.as_view(),
        name="results",
    ),
    path(
        "<path:path>",
        views.TestsView.as_view(),
        name="tests",
    ),
]
