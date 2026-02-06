from dataclasses import dataclass

# Only GitHub is supported for now
HEALTH_STATES = ("pending", "failure", "success")


@dataclass
class Health:
    total: int
    state: str
    description: str

    def __post_init__(self) -> None:
        assert (
            self.state in HEALTH_STATES
        ), f"Unknown state: {self.state!r}, expected one of: {HEALTH_STATES}"

    def __str__(self) -> str:
        return f"{self.description} ({self.state})"
