import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value))


def valid_positive(value: float) -> bool:
    return value is not None and value > 0


class Product:
    def __init__(self, name: str, price: float, supplier_email: str):
        if not valid_positive(price):
            raise ValueError(f"price must be positive: {price}")
        if not valid_email(supplier_email):
            raise ValueError(f"invalid email: {supplier_email}")
        self.name = name
        self.price = price
        self.supplier_email = supplier_email
