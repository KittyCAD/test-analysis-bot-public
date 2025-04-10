from ..models import Project


def describe_project():
    def it_formats_path(expect):
        project = Project(repository="https://github.com/User/repo")
        expect(project.path) == "User / repo"
