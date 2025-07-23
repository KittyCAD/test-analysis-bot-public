from django.urls import path

from . import views

urlpatterns = [
    path("accounts/login/", views.login, name="login"),
    path("accounts/verify/", views.verify, name="verify"),
    path("accounts/logout/", views.logout, name="logout"),
    path("ping", views.ping),
]
