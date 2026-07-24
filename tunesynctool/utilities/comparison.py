from typing import Optional

from thefuzz import fuzz

"""
There wasn't any advanced mathematical thinking behind the following functions.
I found these ways of comparison to be the best for my use case by trial and error lol.
"""

def calculate_str_similarity(a: str, b: str) -> float:
    """
    Calculates the similarity ratio between two strings.
    Returns a float between 1 and 0.
    """

    return fuzz.ratio(a, b) / 100

def calculate_duration_similarity(
    a: Optional[int],
    b: Optional[int],
    gate_seconds: float,
) -> Optional[float]:
    """Score duration proximity without rounding away meaningful seconds."""

    if a is None or b is None or a <= 0 or b <= 0:
        return None

    delta = abs(a - b)
    return max(0.0, 1 - delta / (2 * gate_seconds))


def calculate_year_similarity(
    a: Optional[int],
    b: Optional[int],
) -> Optional[float]:
    """Treat release year as a weak, reissue-tolerant tie-breaker."""

    if a is None or b is None or a <= 0 or b <= 0:
        return None

    delta = abs(a - b)
    if delta == 0:
        return 1.0
    if delta == 1:
        return 0.5
    return 0.0
