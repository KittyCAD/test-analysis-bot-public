from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "<path:path>/tests/<int:test_id>",
        views.TestResultsListView.as_view(),
        name="test-results",
    ),
    path(
        "<path:path>/results",
        views.ResultsListView.as_view(),
        name="results",
    ),
    path(
        "<path:path>",
        views.TestsListView.as_view(),
        name="tests",
    ),
]
