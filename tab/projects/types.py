from dataclasses import dataclass


@dataclass
class Health:
    total: int
    state: str
    description: str
