from django.shortcuts import redirect
from django.urls import path

from ninja import NinjaAPI

from . import views

api = NinjaAPI()


@api.get("/", include_in_schema=False)
def index(request):
    return redirect("/api/docs")


api.add_router("", views.router)

urlpatterns = [
    path("", api.urls),
]
