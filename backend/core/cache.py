import time
from collections import OrderedDict


class TTLCache:
    """Кэш в памяти. Просроченные записи НЕ удаляются (нужны как запасной вариант
    при падении провайдера), вытесняются только по LRU."""

    def __init__(self, max_items: int = 1500):
        self._d: OrderedDict = OrderedDict()
        self.max = max_items

    def get(self, key):
        it = self._d.get(key)
        if it is None:
            return None, False
        exp, val = it
        self._d.move_to_end(key)
        return val, time.time() < exp

    def set(self, key, val, ttl: float):
        self._d[key] = (time.time() + ttl, val)
        self._d.move_to_end(key)
        while len(self._d) > self.max:
            self._d.popitem(last=False)

    def delete(self, key):
        self._d.pop(key, None)

    def size(self) -> int:
        return len(self._d)
