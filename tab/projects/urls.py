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
        "<path:path>/tests/<int:test_id>/results/<int:result_id>",
        views.TestResultView.as_view(),
        name="test-result",
    ),
    path(
        "_result-details/<int:result_id>",
        views.ResultDetailsView.as_view(),
        name="result-details",
    ),
    path(
        "<path:path>/results",
        views.ResultsView.as_view(),
        name="results",
    ),
    path(
        "<path:path>/results/suite/<int:suite_id>",
        views.ResultsView.as_view(),
        name="suite-results",
    ),
    path(
        "<path:path>/results/regex",
        views.ResultsRegexView.as_view(),
        name="results-regex",
    ),
    path(
        "<path:path>/metrics/download.json",
        views.MetricsDownloadView.as_view(),
        name="metrics-download",
    ),
    path(
        "<path:path>/metrics/raw",
        views.MetricsRawView.as_view(),
        name="metrics-raw",
    ),
    path(
        "<path:path>/metrics",
        views.MetricsView.as_view(),
        name="metrics",
    ),
    path(
        "<path:path>/suite/<int:suite_id>",
        views.TestsView.as_view(),
        name="suite-tests",
    ),
    path(
        "<path:path>",
        views.TestsView.as_view(),
        name="tests",
    ),
]
