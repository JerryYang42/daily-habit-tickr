from __future__ import annotations

import random

import pytest

from habits.core.sortkeys import key_between


def test_open_ended() -> None:
    first = key_between(None, None)
    after = key_between(first, None)
    before = key_between(None, first)
    assert before < first < after


@pytest.mark.parametrize(
    ("a", "b"), [("V", "W"), ("V", "V1"), ("0V", "1"), ("a", "b"), ("Vz", "W")]
)
def test_between_neighbours(a: str, b: str) -> None:
    k = key_between(a, b)
    assert a < k < b
    assert not k.endswith("0")


def test_repeated_inserts_stay_ordered() -> None:
    rng = random.Random(42)
    keys = [key_between(None, None)]
    for _ in range(500):
        i = rng.randrange(len(keys) + 1)
        lo = keys[i - 1] if i > 0 else None
        hi = keys[i] if i < len(keys) else None
        keys.insert(i, key_between(lo, hi))
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


def test_appending_grows_slowly() -> None:
    k: str | None = None
    for _ in range(200):
        k = key_between(k, None)
    assert k is not None and len(k) <= 8


@pytest.mark.parametrize(
    ("a", "b"), [("b", "a"), ("a", "a"), ("a0", None), ("", None), ("a!", None)]
)
def test_rejects_bad_input(a: str, b: str | None) -> None:
    with pytest.raises(ValueError):
        key_between(a, b)
