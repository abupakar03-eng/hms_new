"""Helpers for the laboratory module: reference ranges and abnormal flagging."""

import re
from typing import Optional, Tuple

_NUM = r"[-+]?\d+(?:\.\d+)?"

# Matches "4.0 - 11.0", "4,0 – 11,0", "13-17", "up to 200", "<= 5"
_RANGE_RE = re.compile(rf"({_NUM})\s*(?:-|–|—|to)\s*({_NUM})", re.IGNORECASE)
_LT_RE = re.compile(rf"(?:<|<=|less than|up to|upto|below)\s*({_NUM})", re.IGNORECASE)
_GT_RE = re.compile(rf"(?:>|>=|greater than|above|more than)\s*({_NUM})", re.IGNORECASE)


def parse_reference_range(text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Extract ``(low, high)`` from a human readable reference range.

    Unparseable or qualitative ranges (e.g. ``"Negative"``) return ``(None, None)``
    so the caller can fall back to manual flagging.
    """
    if not text:
        return (None, None)
    text = str(text).strip()

    match = _RANGE_RE.search(text)
    if match:
        low, high = float(match.group(1)), float(match.group(2))
        if low > high:  # tolerate "11 - 4" typos
            low, high = high, low
        return (low, high)

    match = _LT_RE.search(text)
    if match:
        return (None, float(match.group(1)))

    match = _GT_RE.search(text)
    if match:
        return (float(match.group(1)), None)

    # A single number is treated as an exact expected value range.
    match = re.fullmatch(rf"\s*({_NUM})\s*", text)
    if match:
        value = float(match.group(1))
        return (value, value)

    return (None, None)


def reference_range_for_gender(
    gender: Optional[str],
    age: Optional[int],
    general: Optional[str],
    male: Optional[str],
    female: Optional[str],
    child: Optional[str],
) -> Optional[str]:
    """Pick the most specific reference range available for a patient."""
    if age is not None and age < 13 and child:
        return child
    if gender == "Male" and male:
        return male
    if gender == "Female" and female:
        return female
    return general or male or female or child


def compute_flag(
    result: Optional[str],
    reference_range: Optional[str],
    critical_low: Optional[float] = None,
    critical_high: Optional[float] = None,
) -> str:
    """Return the abnormal flag for a single numeric result.

    Values outside the critical limits are reported as ``Critical High`` /
    ``Critical Low``; other out-of-range values as ``High`` / ``Low``.
    """
    if result is None:
        return "Normal"
    raw = str(result).strip()
    if raw == "":
        return "Normal"

    try:
        value = float(raw)
    except (TypeError, ValueError):
        # Qualitative result (e.g. "Positive", "Nil"): flag obvious abnormalities.
        lowered = raw.lower()
        if any(token in lowered for token in ("positive", "reactive", "abnormal", "present", "detected")):
            return "Abnormal"
        return "Normal"

    if critical_low is not None and value < critical_low:
        return "Critical Low"
    if critical_high is not None and value > critical_high:
        return "Critical High"

    low, high = parse_reference_range(reference_range)
    if low is not None and value < low:
        return "Low"
    if high is not None and value > high:
        return "High"
    return "Normal"


ABNORMAL_FLAGS = {"High", "Low", "Critical High", "Critical Low", "Abnormal"}


def is_abnormal(flag: Optional[str]) -> bool:
    return (flag or "Normal") in ABNORMAL_FLAGS


def generate_barcode(order_id: int, sample_type: Optional[str] = None) -> str:
    """Deterministic-ish specimen barcode, unique enough for a single site."""
    import random
    from datetime import datetime

    prefix = re.sub(r"[^A-Za-z]", "", (sample_type or "LAB")).upper()[:3] or "LAB"
    stamp = datetime.now().strftime("%y%m%d%H%M%S")
    return f"{prefix}-{order_id:06d}-{stamp}-{random.randint(100, 999)}"
