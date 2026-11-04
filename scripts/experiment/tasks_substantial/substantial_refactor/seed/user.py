import re


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _is_positive(n: float) -> bool:
    return n is not None and n > 0


class User:
    def __init__(self, name: str, email: str, age: int):
        if not _is_valid_email(email):
            raise ValueError(f"invalid email: {email}")
        if not _is_positive(age):
            raise ValueError(f"age must be positive: {age}")
        self.name = name
        self.email = email
        self.age = age
