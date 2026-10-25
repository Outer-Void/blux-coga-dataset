"""Normalization, exact keys and near-duplicate detection.

A record's text is its instruction plus every key and string value of its input. Normalization lowercases,
replaces every number with `0`, and splits into word tokens, so two records that differ only in numbers or
case normalize to the same tokens. The exact key is the SHA-256 of the normalized token list. Similarity is
the Jaccard index of the 4-token shingle sets.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from dstool.common import sha256_text

TOKEN = re.compile(r"[a-z0-9_]+")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
SHINGLE = 4


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)
    elif isinstance(value, dict):
        for k in sorted(value):
            yield k
            yield from _texts(value[k])


def tokens(instruction: str, input_doc: Any) -> list[str]:
    text = " ".join([instruction, *_texts(input_doc)]).lower()
    return TOKEN.findall(NUMBER.sub("0", text))


def exact_key(toks: list[str]) -> str:
    return sha256_text(" ".join(toks))


def shingles(toks: list[str]) -> frozenset[str]:
    if len(toks) < SHINGLE:
        return frozenset([" ".join(toks)])
    return frozenset(" ".join(toks[i : i + SHINGLE]) for i in range(len(toks) - SHINGLE + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
