"""Typosquat detector — runs before AI scan to catch obvious brand knockoffs.

Catches three patterns without touching the AI:
  1. Levenshtein distance ≤ 2 to a brand domain's eTLD+1 label.
     e.g. `paypa1.com` → `paypal.com` (distance 1)
  2. Homoglyph substitution (`0↔o`, `1↔l`, `rn↔m`, `vv↔w`).
     Runs BEFORE distance so `paypa1` is normalized to `paypal` and
     matches directly.
  3. Brand label appearing with an extra prefix/suffix, e.g.
     `secure-paypal-login.com`, `paypal-account.xyz`.

Stays intentionally simple — no ML, no fuzz hashes, no dicts beyond the
brand list supplied by the resolver at boot (brand_domains table).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


HOMOGLYPHS = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "$": "s", "@": "a", "!": "i",
}
# multi-char replacements (apply before single-char)
MULTI_HOMOGLYPHS = [
    ("rn", "m"),
    ("vv", "w"),
    ("cl", "d"),   # ripe for false positives; kept conservative, only used
                   # after exact-label match fails
]


@dataclass
class TyposquatHit:
    brand: str            # display name, e.g. "PayPal"
    brand_domain: str     # canonical, e.g. "paypal.com"
    reason: str           # human-readable why we matched
    distance: int         # edit distance we measured (0 = normalized exact)


class TyposquatDetector:
    def __init__(self, brand_map: dict[str, str]):
        """
        brand_map: {canonical_domain: brand_name}
                   e.g. {"paypal.com": "PayPal", "apple.com": "Apple", ...}
        """
        self._brands = brand_map
        # Precompute normalized brand labels for fast comparison.
        self._brand_labels = {
            _etld_plus_one_label(dom): (dom, brand)
            for dom, brand in brand_map.items()
        }

    def check(self, domain: str) -> Optional[TyposquatHit]:
        domain = domain.lower().strip(".")
        label = _etld_plus_one_label(domain)
        if not label:
            return None

        # Fast path: exact match against a brand label → not a typosquat,
        # caller should treat as the real brand (resolver already checked
        # whitelist separately).
        if label in self._brand_labels:
            return None

        # 1) Normalize homoglyphs, check exact match after normalization.
        normalized = _normalize(label)
        if normalized != label and normalized in self._brand_labels:
            canonical, brand = self._brand_labels[normalized]
            return TyposquatHit(
                brand=brand,
                brand_domain=canonical,
                reason=f"homoglyph of {brand} ({label} looks like {normalized})",
                distance=0,
            )

        # 2) Edit distance to any brand label. Allow distance ≤ 1 for any
        # brand, distance ≤ 2 only when the brand label is long enough that
        # two edits don't collapse into an unrelated word (guards against
        # 'snapple' → 'apple' false positives).
        for brand_label, (canonical, brand) in self._brand_labels.items():
            max_d = 2 if len(brand_label) >= 7 else 1
            if abs(len(brand_label) - len(label)) > max_d:
                continue
            d = _levenshtein(label, brand_label, max_distance=max_d)
            if d is not None and 0 < d <= max_d:
                return TyposquatHit(
                    brand=brand,
                    brand_domain=canonical,
                    reason=f"edit distance {d} from {canonical}",
                    distance=d,
                )

        # 3) Brand label appears as a token inside a longer label — e.g.
        # 'secure-paypal-login' or 'paypal-account'. Requires the brand to
        # sit at a word boundary (start/end of label or next to '-'/'_') so
        # substring matches like 'apple' ⊂ 'snapple' don't trigger.
        # Check on BOTH raw and normalized label so 'app1e-support' catches
        # 'apple' after 1→l.
        for candidate_label in {label, normalized}:
            for brand_label, (canonical, brand) in self._brand_labels.items():
                if len(brand_label) < 5:
                    continue
                if _contains_at_boundary(candidate_label, brand_label):
                    return TyposquatHit(
                        brand=brand,
                        brand_domain=canonical,
                        reason=f"contains brand '{brand}' in non-official domain",
                        distance=0,
                    )

        return None


# ---------------------------------------------------------------------------

def _contains_at_boundary(label: str, brand: str) -> bool:
    """True when `brand` appears in `label` as its own token — at the start,
    end, or separated by '-' or '_'. Avoids 'apple' ⊂ 'snapple' false hits."""
    if label == brand:
        return False
    idx = 0
    while True:
        i = label.find(brand, idx)
        if i == -1:
            return False
        left_ok = i == 0 or label[i - 1] in "-_"
        end = i + len(brand)
        right_ok = end == len(label) or label[end] in "-_"
        if left_ok and right_ok:
            return True
        idx = i + 1


def _etld_plus_one_label(domain: str) -> str:
    """Return the leading label of the eTLD+1. Rough heuristic — we don't
    parse PSL. For 'login.paypal.com' returns 'paypal'. For 'paypal.co.uk'
    returns 'paypal'. Good enough for brand matching."""
    parts = domain.split(".")
    if len(parts) < 2:
        return ""
    # Compound TLDs we care about (.co.uk, .com.my, etc.)
    compound = {"co.uk", "com.my", "com.au", "com.sg", "com.br", "co.jp", "co.kr", "com.cn"}
    tail = ".".join(parts[-2:])
    if tail in compound and len(parts) >= 3:
        return parts[-3]
    return parts[-2]


def _normalize(s: str) -> str:
    out = s
    for src, dst in MULTI_HOMOGLYPHS:
        out = out.replace(src, dst)
    out = "".join(HOMOGLYPHS.get(ch, ch) for ch in out)
    return out


def _levenshtein(a: str, b: str, max_distance: int = 2) -> Optional[int]:
    """Returns the edit distance, or None if it's guaranteed to exceed
    max_distance. Early-exit saves time when scanning many brands."""
    if abs(len(a) - len(b)) > max_distance:
        return None
    if a == b:
        return 0

    # Two-row DP.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                curr[j - 1] + 1,        # insertion
                prev[j] + 1,            # deletion
                prev[j - 1] + cost,     # substitution
            )
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_distance:
            return None
        prev = curr
    return prev[-1]


def build_brand_map(rows: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Helper to build the map the detector expects from DB rows."""
    return {domain: brand for domain, brand in rows}
