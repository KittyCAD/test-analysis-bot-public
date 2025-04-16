from ..enums import Platform, Status, Target


def describe_status():
    def describe_normalize():
        def it_detects_expected_failures(expect):
            expect(
                Status.normalize(
                    "failed", markers=["fail"], message="", error_indicators=[]
                )
            ) == "xfailed"

        def it_detects_unexpected_passes(expect):
            expect(
                Status.normalize(
                    "passed", markers=["fail"], message="", error_indicators=[]
                )
            ) == "xpassed"

        def it_detects_expected_broken(expect):
            expect(
                Status.normalize(
                    "error", markers=["fixme"], message="", error_indicators=[]
                )
            ) == "disabled"

        def it_detects_errors(expect):
            expect(
                Status.normalize(
                    "failed",
                    markers=[],
                    message="Call log:\n  - waiting for getByTestId('overlay-menu')",
                    error_indicators=["waiting for getByTestId('overlay-menu')"],
                )
            ) == "error"


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
