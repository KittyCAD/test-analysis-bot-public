from dataclasses import dataclass


@dataclass
class Health:
    total: int
    state: str
    description: str

    def __str__(self) -> str:
        return f"{self.description} ({self.state})"
