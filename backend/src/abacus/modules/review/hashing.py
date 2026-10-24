"""Content hashes for reviewables (P-04-T14; ADR-160; DEC-215).

A sign-off records the hash of what it approved; a sign-off is stale exactly when its hash differs
from the target's current hash. Every owner hashes its content the same way: the value is put in
canonical JSON under the rules of RFC 8785 (the JSON Canonicalization Scheme), implemented here
without a dependency, and the UTF-8 bytes are hashed with SHA-256 (lowercase hex).

The RFC 8785 rules, as applied:

- no whitespace; `null`, `true`, `false` as literals;
- strings: UTF-8, with only `"`, `\\` and the control characters below U+0020 escaped
  (`\\b \\f \\n \\r \\t` in short form, the rest as `\\u00xx` in lowercase hex); everything else,
  including U+2028 and U+2029, is written as itself. A lone surrogate is refused;
- numbers: the ECMAScript `Number.prototype.toString` form of the IEEE 754 double (shortest
  round-trip digits; `1e+21`, `1e-7`; `-0` is `0`). NaN and infinities are refused, and so is an
  integer the double cannot hold exactly (beyond 2**53 - 1), so nothing is rounded silently;
- object members sorted by their names' UTF-16 code units; arrays keep their order.

Money and other decimals are hashed as strings (`{"t": "decimal", "v": "2310.00"}`): a `Decimal`
is refused, so no amount ever passes through a double (ADR-050).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, cast

# Anything JSON can carry; values are checked at run time.
Json = None | bool | int | float | str | Sequence["Json"] | Mapping[str, "Json"]

MAX_SAFE_INTEGER: Final = 2**53 - 1
_SHORT: Final = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


class NotCanonical(ValueError):
    """A value RFC 8785 cannot represent exactly (or that this platform refuses to hash)."""


def _string(text: str) -> str:
    out = ['"']
    for ch in text:
        if ch in _SHORT:
            out.append(_SHORT[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        elif 0xD800 <= ord(ch) <= 0xDFFF:
            raise NotCanonical("a lone surrogate has no UTF-8 form")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _number(value: float) -> str:
    """ECMAScript Number.prototype.toString for a finite double (ECMA-262 §6.1.6.1.20)."""
    if not math.isfinite(value):
        raise NotCanonical("NaN and infinities have no JSON form")
    if value == 0:
        return "0"  # -0 too
    sign = "-" if value < 0 else ""
    # repr is the shortest string that round-trips, the same digits ECMAScript chooses.
    shortest = Decimal(repr(abs(value))).as_tuple()
    digits_tuple, exponent = shortest.digits, int(shortest.exponent)  # finite: an int
    digits = "".join(str(d) for d in digits_tuple).rstrip("0")
    # Decimal(repr(x)) = int(all digits) * 10**exponent; with trailing zeros stripped:
    trailing = len(digits_tuple) - len(digits)
    k = len(digits)
    n = exponent + trailing + k  # value = 0.digits * 10**n
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
    return f"{sign}{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def _utf16(key: str) -> bytes:
    return key.encode("utf-16-be", errors="surrogatepass")


def _write(value: object, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise NotCanonical("an integer beyond 2**53 - 1 is not exact as a double")
        out.append(str(value))
    elif isinstance(value, float):
        out.append(_number(value))
    elif isinstance(value, str):
        out.append(_string(value))
    elif isinstance(value, Decimal):
        raise NotCanonical("decimals are hashed as strings, never as numbers")
    elif isinstance(value, Mapping):
        named: list[tuple[str, object]] = []
        for key, member in cast(Mapping[object, object], value).items():
            if not isinstance(key, str):
                raise NotCanonical("object member names are strings")
            named.append((key, member))
        out.append("{")
        for index, (key, member) in enumerate(sorted(named, key=lambda m: _utf16(m[0]))):
            if index:
                out.append(",")
            out.append(_string(key))
            out.append(":")
            _write(member, out)
        out.append("}")
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, member in enumerate(cast(Sequence[object], value)):
            if index:
                out.append(",")
            _write(member, out)
        out.append("]")
    else:
        raise NotCanonical(f"{type(value).__name__} has no JSON form")


def canonical_json(value: Json) -> bytes:
    """The RFC 8785 canonical form of `value`, as UTF-8 bytes."""
    out: list[str] = []
    _write(value, out)
    return "".join(out).encode("utf-8")


def content_hash(value: Json) -> str:
    """SHA-256 of the canonical JSON, lowercase hex: what a sign-off records."""
    return hashlib.sha256(canonical_json(value)).hexdigest()
