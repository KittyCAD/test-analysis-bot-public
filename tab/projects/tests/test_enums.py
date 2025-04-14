from ..enums import Platform, Status, Target


def describe_status():
    def it_normalizes_values(expect):
        expect(Status.normalize("failed", annotations=["fail"])) == "xfailed"
        expect(Status.normalize("passed", annotations=["fail"])) == "xpassed"
        expect(Status.normalize("failed", annotations=[])) == "failed"


def describe_target():
    def it_normalizes_values(expect):
        expect(Target.normalize("browser")) == "web"
        expect(Target.normalize("web")) == "web"
        expect(Target.normalize("Website")) == "web"
        expect(Target.normalize("desktop")) == "desktop"
        expect(Target.normalize("Electron")) == "desktop"


def describe_platform():
    def it_normalizes_values(expect):
        expect(Platform.normalize("macOS")) == "macos"
        expect(Platform.normalize("darwin")) == "macos"
        expect(Platform.normalize("Windows")) == "windows"
        expect(Platform.normalize("win32")) == "windows"
        expect(Platform.normalize("linux")) == "linux"
        expect(Platform.normalize("Ubuntu")) == "linux"
