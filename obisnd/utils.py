"""
Cross-cutting helpers that don't belong to any single external system.

Anything that touches GBIF, OBIS, or GitHub specifically should live in
the corresponding module (`gbif.py`, `obis.py`, `github.py`). This file
is reserved for utilities used across multiple modules.
"""

from typing import Iterable


def normalize_url(url: str) -> str:
    """Normalize a URL for string-equality matching.

    The only normalization applied is forcing the scheme to ``http://``.
    Some IPTs were registered to GBIF/OBIS under ``http://`` and some
    under ``https://``; collapsing both to one form prevents spurious
    mismatches. No other transformations are applied (no trailing-slash
    stripping, no case folding, no query-string changes).

    Args:
        url: A URL string. ``None`` and empty strings are returned unchanged.

    Returns:
        The URL with any leading ``https://`` replaced by ``http://``.
    """
    if not url:
        return url
    if url.startswith("https://"):
        return "http://" + url[len("https://"):]
    return url


def urls_match(candidate_urls: Iterable, target_urls: Iterable) -> bool:
    """Return True if any candidate URL appears in the target URL list.

    Both inputs are normalized via :func:`normalize_url` before
    comparison, so callers do not need to pre-normalize. Comparison is
    exact string equality after normalization.

    Args:
        candidate_urls: URLs to look for (e.g. identifiers from a GBIF
            dataset, or URLs extracted from an issue body).
        target_urls: URLs to look in (e.g. all known OBIS source URLs,
            or URLs from one OBIS dataset record).

    Returns:
        True if at least one normalized candidate appears in the
        normalized target list. False if either input is empty or no
        candidate matches.
    """
    targets = {normalize_url(u) for u in target_urls if u}
    if not targets:
        return False
    for url in candidate_urls:
        if not url:
            continue
        if normalize_url(url) in targets:
            return True
    return False