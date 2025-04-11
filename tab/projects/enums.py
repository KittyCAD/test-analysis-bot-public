from django.db import models


class Status(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"

    TIMED_OUT = "timedOut", "Timed Out"
    INTERRUPTED = "interrupted", "Interrupted"


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
