import queue
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


class ThrottledClient[T]:
    """
    A wrapper around a client that throttles the number of concurrent requests.

    Args:
        client: The client to wrap.
        queue_size: The number of concurrent requests to allow.
        timeout: The timeout for requests.

    Example Usage:
        ```python
        client = ThrottledClient(boto3.client("s3"), queue_size=10, timeout=20)
        client.head_object(Bucket="my-bucket", Key="my-key")
        ```
    """

    def __init__(self, client: T, queue_size: int = 10, timeout: int = 20):
        self._client = client
        self._queue = queue.Queue(maxsize=queue_size)
        self._timeout = timeout

        # Initialize the queue with a token for each allowed concurrent request
        for _ in range(queue_size):
            self._queue.put(object())

    def _call(self, name: str, *args: P.args, **kwargs: P.kwargs) -> R:
        """
        Call the underlying client method and return the result. This pulls a token from
        the queue, blocking until one is available.

        Args:
            name: The name of the method to call.
            args: The arguments to pass to the method.
            kwargs: The keyword arguments to pass to the method.

        Returns:
            The result of the method call.
        """
        token = self._queue.get(timeout=self._timeout)

        try:
            return self._client.__getattribute__(name)(*args, **kwargs)
        finally:
            self._queue.put(token)

    def __getattr__(self, name: str) -> Callable[P, R]:
        """Wrap the underlying client method with a token from the queue."""

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return self._call(name, *args, **kwargs)

        return wrapper
