from ..models import Project


def describe_project():
    def it_formats_name(expect):
        project = Project(repository="https://github.com/User/repo")
        expect(project.name) == "User › repo"
