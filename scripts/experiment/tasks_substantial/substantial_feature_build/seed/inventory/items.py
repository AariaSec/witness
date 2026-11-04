class Item:
    def __init__(self, name: str, price: float, qty: int = 0):
        self.name = name
        self.price = price
        self.qty = qty


class Inventory:
    def __init__(self):
        self._items: list[Item] = []

    def add(self, item: Item) -> None:
        self._items.append(item)

    def all(self) -> list[Item]:
        return list(self._items)

    def total_value(self) -> float:
        return sum(i.price * i.qty for i in self._items)
