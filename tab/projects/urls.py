from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.index, name="index"),
    path("<path:path>", views.detail, name="detail"),
]
