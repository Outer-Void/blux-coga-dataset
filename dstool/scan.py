"""Privacy and hidden-reasoning scanners. Both are gates: a record with a hit is never built.

Privacy: e-mail addresses outside the reserved example domains, phone numbers, IPv4 addresses outside the
documentation and loopback ranges, home-directory paths, private keys and well-known credential formats,
and any term listed in the untracked file `.private-terms` (one per line). The deny list lives outside
version control so private names are never published by listing them.

Hidden reasoning: object keys that name model reasoning (`thought`, `chain_of_thought`, `scratchpad`,
`hidden_reasoning`, `inner_monologue`, `reasoning_trace` …) and text markers such as `<thinking>`. An
adversarial record may contain such a key only inside its input request, only with a short value, and only
when the engine rejected the request: it then records an attempt to smuggle reasoning, not reasoning.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "example.invalid", "users.noreply.github.com")
PHONE = re.compile(r"(?<![\w.])\+?\d{1,3}[ .-]?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\w.])")
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
DOC_NETS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "127.0.0.0/8", "0.0.0.0/32", "10.0.0.0/8")
]
HOME = re.compile(
    r"(/home/[a-z_][a-z0-9_-]*|/Users/[A-Za-z0-9_-]+|[A-Za-z]:\\Users\\[A-Za-z0-9_-]+|/data/data/[a-z]+\.[a-z.]+)"
)
ALLOWED_HOME = ("/home/user", "/home/app", "/Users/user", "/home/runner")
CREDENTIAL = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|sk-[A-Za-z0-9]{32,}|AIza[0-9A-Za-z_-]{35})"
)
COT_KEYS = re.compile(
    r"^(thoughts?|chain[_-]?of[_-]?thought|cot|scratch[_-]?pad|hidden[_-]?reasoning|reasoning[_-]?trace"
    r"|inner[_-]?monologue|internal[_-]?reasoning|thinking)$",
    re.I,
)
COT_TEXT = re.compile(r"(<\s*/?\s*(thinking|scratchpad|reasoning)\s*>|\bchain[- ]of[- ]thought\b)", re.I)


def private_terms(root: Path) -> list[str]:
    path = root / ".private-terms"
    if not path.is_file():
        return []
    return [t.strip() for t in path.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]


def _strings(doc: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(doc, str):
        yield path, doc
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from _strings(v, f"{path}/{i}")
    elif isinstance(doc, dict):
        for k, v in doc.items():
            yield f"{path}/{k}#key", k
            yield from _strings(v, f"{path}/{k}")


def privacy_hits(doc: Any, terms: list[str]) -> list[str]:
    hits = []
    for where, text in _strings(doc):
        for m in EMAIL.finditer(text):
            if not m.group(0).lower().endswith(ALLOWED_EMAIL_DOMAINS):
                hits.append(f"{where}: e-mail address")
        if PHONE.search(text):
            hits.append(f"{where}: phone number")
        for m in IPV4.finditer(text):
            try:
                ip = ipaddress.ip_address(m[1])
            except ValueError:
                continue
            if not any(ip in n for n in DOC_NETS):
                hits.append(f"{where}: IPv4 address outside documentation ranges")
        for m in HOME.finditer(text):
            if not m.group(0).startswith(ALLOWED_HOME):
                hits.append(f"{where}: home-directory path")
        if CREDENTIAL.search(text):
            hits.append(f"{where}: credential or private key")
        lowered = text.lower()
        hits.extend(f"{where}: private term" for t in terms if t.lower() in lowered)
    return sorted(set(hits))


def _keys(doc: Any, path: str = "") -> Iterator[tuple[str, str, Any]]:
    if isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from _keys(v, f"{path}/{i}")
    elif isinstance(doc, dict):
        for k, v in doc.items():
            yield f"{path}/{k}", k, v
            yield from _keys(v, f"{path}/{k}")


def reasoning_hits(record: dict[str, Any], *, rejected: bool) -> list[str]:
    hits = []
    for where, key, value in _keys(record):
        if COT_KEYS.match(key):
            allowed = (
                record.get("split") == "adversarial"
                and rejected
                and where.startswith("/input/request/")
                and isinstance(value, str)
                and len(value) <= 64
            )
            if not allowed:
                hits.append(f"{where}: key names model reasoning")
    for where, text in _strings(record):
        if COT_TEXT.search(text):
            hits.append(f"{where}: hidden-reasoning marker")
    return sorted(set(hits))
