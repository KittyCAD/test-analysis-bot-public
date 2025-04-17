from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "<path:path>/tests/<int:test_id>",
        views.ResultListView.as_view(),
        name="test-detail",
    ),
    path("<path:path>", views.TestListView.as_view(), name="detail"),
]
