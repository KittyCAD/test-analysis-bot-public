import pytest

from ..models import Platform, Project, Result


def describe_project():
    def it_formats_name(expect):
        project = Project(repository="https://github.com/MyUser/my_repo")
        expect(project.name) == "MyUser › my_repo"


def describe_platform():
    def it_normalizes_values(expect):
        expect(Platform.normalize("macOS")) == "macos"
        expect(Platform.normalize("darwin")) == "macos"
        expect(Platform.normalize("Windows")) == "windows"
        expect(Platform.normalize("win32")) == "windows"
        expect(Platform.normalize("linux")) == "linux"
        expect(Platform.normalize("Ubuntu")) == "linux"


def describe_result():
    def describe_save():
        @pytest.mark.django_db
        def it_cleans_message(expect):
            test = Project.objects.create(
                repository="https://github.com/foo/bar"
            ).test_set.create(name="test")
            result = Result.objects.create(
                test=test,
                status="failed",
                branch="main",
                commit="abc123",
                message="Error: [31mTimed out 5000ms waiting for [39m[2mexpect([22m[31mlocator[39m[2m).[22mnot[2m.[22mtoBeDisabled[2m()[22m",
            )
            expect(
                result.message
            ) == "Error: Timed out 5000ms waiting for expect(locator).not.toBeDisabled()"
