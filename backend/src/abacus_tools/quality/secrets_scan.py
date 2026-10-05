"""Secrets and real-identifier scan of tracked files (ADR-083 stage 1, ADR-085). PROTECTED.

Run: python -m abacus_tools.quality.secrets_scan

Scans what git tracks (including staged files). Messages never echo the matched value, because
they end up in CI logs. Exceptions only via EXCLUDE globs in this file. Synthetic data must use
reserved ranges (SSN area 9xx, published test card numbers) so it never trips these rules.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from abacus_tools.quality.banned_patterns import Finding, Violation

REPO = Path(__file__).resolve().parents[4]
MAX_BYTES = 1_000_000
LOCKFILES = frozenset({"uv.lock", "pnpm-lock.yaml"})
EXCLUDE: tuple[str, ...] = ()
DATA_SUFFIXES = frozenset({".csv", ".json", ".yaml", ".yml", ".txt", ".tsv"})
CONFIG_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".yaml", ".yml", ".toml"}
)


@dataclass(frozen=True)
class TextFile:
    rel: str
    lines: list[str]

    @property
    def suffix(self) -> str:
        return PurePosixPath(self.rel).suffix.lower()

    @property
    def is_env(self) -> bool:
        return PurePosixPath(self.rel).name.lower().startswith(".env")


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    adr: str
    check: Callable[[TextFile], Iterator[Finding]]


# --- SECRET-001 private keys ------------------------------------------------------------------

_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")


def _check_private_key(f: TextFile) -> Iterator[Finding]:
    for n, line in enumerate(f.lines, start=1):
        if _PRIVATE_KEY.search(line):
            yield Finding(n, "private key block")


# --- SECRET-002 provider tokens ---------------------------------------------------------------

_TOKENS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI project key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9]{48}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Stripe live key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}")),
)


def _check_provider_token(f: TextFile) -> Iterator[Finding]:
    for n, line in enumerate(f.lines, start=1):
        for label, pattern in _TOKENS:
            if pattern.search(line):
                yield Finding(n, label)


# --- SECRET-003 credential assignments --------------------------------------------------------

_CRED_NAME = r"[A-Za-z0-9_.-]*(?:key|secret|token|passwd|password)[A-Za-z0-9_.-]*"
_QUOTED = re.compile(
    rf"(?i)(?<![A-Za-z0-9_])[\"']?{_CRED_NAME}[\"']?"
    r"(?:\s*:\s*[A-Za-z_][\w\[\]., |]*)?\s*[:=]\s*([\"'])(?P<value>[^\"']*)\1"
)
_BARE = re.compile(
    rf"(?i)^\s*(?:export\s+)?{_CRED_NAME}\s*[:=]\s*(?P<value>[^\s\"'#]+)\s*(?:#.*)?$"
)
_PLACEHOLDER_WORDS = (
    "changeme",
    "example",
    "placeholder",
    "dummy",
    "fake",
    "test",
    "xxx",
    "redacted",
)


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return (
        not value
        or value.startswith(("<", "${", "{{", "$"))
        or any(word in lowered for word in _PLACEHOLDER_WORDS)
        or len(set(value)) == 1
    )


def _is_credential(value: str) -> bool:
    return len(value) >= 8 and not any(c.isspace() for c in value) and not _is_placeholder(value)


def _check_credential_assignment(f: TextFile) -> Iterator[Finding]:
    if not f.is_env and f.suffix not in CONFIG_SUFFIXES:
        return
    bare_allowed = f.is_env or f.suffix in {".yaml", ".yml"}
    for n, line in enumerate(f.lines, start=1):
        quoted = [m.group("value") for m in _QUOTED.finditer(line)]
        bare = _BARE.match(line) if bare_allowed else None
        values = quoted + ([bare.group("value")] if bare else [])
        if any(_is_credential(v) for v in values):
            yield Finding(n, "credential assigned to a key/secret/token/password name")


# --- PII rules --------------------------------------------------------------------------------

_SSN = re.compile(r"\b(\d{3})-(\d{2})-(\d{4})\b")
_EIN = re.compile(r"\b(\d{2})-\d{7}\b")
_EIN_PREFIXES = frozenset(
    [
        *range(1, 7),
        *range(10, 17),
        *range(20, 28),
        *range(30, 49),
        *range(50, 69),
        *range(71, 78),
        *range(80, 89),
        *range(90, 96),
        98,
        99,
    ]
)
_CARD = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")
_ROUTING = re.compile(r"(?<!\d)\d{9}(?!\d)")
_ROUTING_LABEL = re.compile(r"(?i)\b(?:routing|aba)\b")
TEST_CARDS = frozenset(
    {
        "4111111111111111",
        "4242424242424242",
        "5555555555554444",
        "5105105105105100",
        "378282246310005",
        "371449635398431",
        "6011111111111117",
        "3530111333300000",
    }
)


def _check_ssn(f: TextFile) -> Iterator[Finding]:
    for n, line in enumerate(f.lines, start=1):
        for m in _SSN.finditer(line):
            area, group, serial = m.groups()
            reserved = area in {"000", "666"} or area.startswith("9")
            if not reserved and group != "00" and serial != "0000":
                yield Finding(n, "value shaped like a real SSN")


def _check_ein(f: TextFile) -> Iterator[Finding]:
    if f.suffix not in DATA_SUFFIXES:
        return
    for n, line in enumerate(f.lines, start=1):
        if any(int(m.group(1)) in _EIN_PREFIXES for m in _EIN.finditer(line)):
            yield Finding(n, "value shaped like a real EIN")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _aba(digits: str) -> bool:
    d = [int(c) for c in digits]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + d[2] + d[5] + d[8]) % 10 == 0


def _check_financial_number(f: TextFile) -> Iterator[Finding]:
    for n, line in enumerate(f.lines, start=1):
        cards = (re.sub(r"[ -]", "", m.group()) for m in _CARD.finditer(line))
        if any(_luhn(c) and c not in TEST_CARDS for c in cards if 13 <= len(c) <= 19):
            yield Finding(n, "value shaped like a real card number")
        if _ROUTING_LABEL.search(line) and any(_aba(m.group()) for m in _ROUTING.finditer(line)):
            yield Finding(n, "value shaped like a real bank routing number")


RULES: list[Rule] = [
    Rule("SECRET-001", "Private keys", "ADR-083", _check_private_key),
    Rule("SECRET-002", "Provider tokens", "ADR-083", _check_provider_token),
    Rule("SECRET-003", "Credentials assigned to names", "ADR-083", _check_credential_assignment),
    Rule("PII-001", "Real-looking SSNs", "ADR-085", _check_ssn),
    Rule("PII-002", "Real-looking EINs in data files", "ADR-085", _check_ein),
    Rule("PII-003", "Card and routing numbers", "ADR-085", _check_financial_number),
]


# --- runner -----------------------------------------------------------------------------------


def _tracked_files(repo: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to list tracked files")
    out = subprocess.run(
        [git, "ls-files", "-z"], cwd=repo, capture_output=True, check=True
    ).stdout.decode()
    return [p for p in out.split("\0") if p]


def _load(repo: Path, rel: str) -> TextFile | None:
    if PurePosixPath(rel).name in LOCKFILES or any(fnmatch(rel, g) for g in EXCLUDE):
        return None
    path = repo / rel
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        return None
    data = path.read_bytes()
    if b"\0" in data:
        return None
    return TextFile(rel, data.decode("utf-8", errors="replace").splitlines())


def scan(repo: Path = REPO, files: Iterable[str] | None = None) -> list[Violation]:
    violations: list[Violation] = []
    for rel in _tracked_files(repo) if files is None else files:
        text = _load(repo, rel)
        if text is None:
            continue
        for rule in RULES:
            for f in rule.check(text):
                violations.append(Violation(rel, f.line, rule.id, f.message, rule.adr))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule_id))


def main() -> int:
    violations = scan()
    for v in violations:
        print(v)
    if violations:
        print(f"{len(violations)} secret or identifier finding(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
