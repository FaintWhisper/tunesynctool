from itertools import islice
from typing import Any, Generator, Iterable

def batch(items: Iterable[Any], chunk_size: int) -> Generator[tuple, Any, None]:
    """
    Split a list of tracks into batches of a given size.

    :param items: The items to split.
    :param chunk_size: The size of each batch.
    :return: Tuples containing at most ``chunk_size`` items.
    """

    iterator = iter(items)
    while chunk := tuple(islice(iterator, chunk_size)):
        yield chunk
