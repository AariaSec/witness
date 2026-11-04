import re


def check_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def check_positive(n: float) -> bool:
    return n is not None and n > 0


class Order:
    def __init__(self, customer_email: str, total: float):
        if not check_email(customer_email):
            raise ValueError(f"invalid email: {customer_email}")
        if not check_positive(total):
            raise ValueError(f"total must be positive: {total}")
        self.customer_email = customer_email
        self.total = total
