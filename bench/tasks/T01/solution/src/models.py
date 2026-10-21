from dataclasses import dataclass


@dataclass
class User:
    id: int = 0
    name: str = ''
    email: str = ''
