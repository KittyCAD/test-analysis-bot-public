from django.db import models


class Status(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"

    ERROR = "error", "Setup Error"
    TIMEDOUT = "timedOut", "Timed Out"
    INTERRUPTED = "interrupted", "Interrupted"

    XFAILED = "xfailed", "Expected Failure"
    XPASSED = "xpassed", "Unexpected Pass"

    @classmethod
    def normalize(
        cls,
        value: str,
        *,
        annotations: list[str],
        message: str | None,
        error_indicators: list[str],
    ) -> str:
        if value == cls.FAILED.value and "fail" in annotations:
            return cls.XFAILED.value
        if value == cls.PASSED.value and "fail" in annotations:
            return cls.XPASSED.value
        if message:
            for error_indicator in error_indicators:
                if error_indicator in message:
                    return cls.ERROR.value
        return value

    @property
    def color(self):
        match self:
            case self.PASSED | self.XFAILED:
                return "success"
            case self.FAILED | self.XPASSED:
                return "danger"
            case self.ERROR | self.TIMEDOUT:
                return "warning"
            case self.SKIPPED | self.INTERRUPTED:
                return "secondary"
            case _:
                return "dark"


class Target(models.TextChoices):
    WEB = "web", "Web"
    DESKTOP = "desktop", "Desktop"

    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.lower()
        if "web" in value or "browser" in value:
            return cls.WEB.value
        elif "desktop" in value or "electron" in value:
            return cls.DESKTOP.value
        else:
            raise ValueError(f"Unknown target: {value}")


class Platform(models.TextChoices):
    MACOS = "macos", "macOS"
    WINDOWS = "windows", "Windows"
    LINUX = "linux", "Linux"

    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.lower()
        if "mac" in value or "darwin" in value:
            return cls.MACOS.value
        elif "win" in value:
            return cls.WINDOWS.value
        elif "linux" in value or "ubuntu" in value:
            return cls.LINUX.value
        else:
            raise ValueError(f"Unknown platform: {value}")
