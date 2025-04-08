from django.shortcuts import get_object_or_404, redirect

from ninja import NinjaAPI

from tab.projects.models import Project

api = NinjaAPI()


@api.get("/", include_in_schema=False)
def index(request):
    return redirect("/api/docs")


@api.post("/results")
def results(request, repository: str):
    project = get_object_or_404(Project, repository=repository)
    return {"project": str(project)}
