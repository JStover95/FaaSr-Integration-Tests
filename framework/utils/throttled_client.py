import queue
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class ThrottledClient[T]:
    def __init__(self, client: T, queue_size: int = 10, timeout: int = 20):
        self._client = client
        self._queue = queue.Queue(maxsize=queue_size)
        self._timeout = timeout

        for _ in range(queue_size):
            self._queue.put(object())

    def _call(self, name: str, *args: P.args, **kwargs: P.kwargs) -> R:
        token = self._queue.get(timeout=self._timeout)
        try:
            return self._client.__getattribute__(name)(*args, **kwargs)
        finally:
            self._queue.put(token)

    def __getattr__(self, name: str) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return self._call(name, *args, **kwargs)

        return wrapper
