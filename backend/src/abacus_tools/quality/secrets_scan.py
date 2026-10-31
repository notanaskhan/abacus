"""Secrets and real-identifier scan of tracked files (ADR-083 stage 1, ADR-085). PROTECTED.

Run: python -m abacus_tools.quality.secrets_scan            (tracked files)
     python -m abacus_tools.quality.secrets_scan --history  (every blob on every ref)

Scans what git tracks (including staged files), or with --history every blob reachable from any
ref, reporting the rule, path and commit. Messages never echo the matched value, because they end
up in CI logs. Exceptions only via EXCLUDE globs and ALLOW entries in this file; every ALLOW entry
names a reason. Synthetic data must use
reserved ranges (SSN area 9xx, published test card numbers) so it never trips these rules.
"""

from __future__ import annotations

import codecs
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
# (path glob, rule id, reason): findings that are known local fixtures, never real secrets.
ALLOW: tuple[tuple[str, str, str], ...] = (
    (
        "backend/tests/unit/sampling/test_a03t07_populations.py",
        "PII-001",
        "synthetic SSN-shaped values under an innocent header, proving a population's column map"
        " refuses a Restricted column by its values (A-03-T07); never a real person's number",
    ),
    (
        "backend/tests/unit/integrations/test_task2152_esign_install_tool.py",
        "SECRET-003",
        "a synthetic DocuSeal-shaped key that spells 'not a secret', for the install tool's"
        " shape check (TASK-2152); never a real key",
    ),
    (
        "backend/migrations/bootstrap-local.sql",
        "*",
        "local-only database role passwords for the docker compose stack;"
        " never used in a hosted database",
    ),
    (
        "docker-compose.yml",
        "*",
        "local S3 gateway root key (ROOT_SECRET_KEY: abacuslocal)"
        " for the docker compose stack only",
    ),
    (
        "backend/tests/workflows/histories/*.json",
        "SECRET-003",
        "Temporal replay histories record the payload codec's encryption-key-id,"
        " the key's name (platform-v1), not key material",
    ),
    (
        "backend/tests/contracts/review_grammar/test_c3_shl10_proposals.py",
        "SECRET-003",
        "C3 `field_key` values are tax-form line codes (f1040.l2a, sch_a.l5b), not credentials",
    ),
    (
        "backend/tests/unit/integrations/test_task2152_esign_install_tool.py",
        "SECRET-003",
        "N-02-T18: a synthetic key literal (synthetic0key0not0a0secret0…) for the install tool's"
        " shape check, not a credential",
    ),
    (
        "backend/tests/unit/methodology/test_k02t11_standards_workbooks.py",
        "SECRET-003",
        "K-02-T11: firm-standard item keys (k1.basis, m1.tie), not credentials",
    ),
    (
        "backend/tests/unit/reporting/test_t01t17_consent_templates.py",
        "SECRET-003",
        "T-01-T17: report `layout_key` names (consent_7216), not credentials",
    ),
    (
        "backend/tests/unit/tax/test_t01t10_consent_capture.py",
        "SECRET-003",
        "T-01-T10: report `layout_key` names (consent_7216), not credentials",
    ),
    (
        "backend/tests/integration/backfill/test_k01t12_programs_read.py",
        "SECRET-003",
        "K-01-T12: methodology step keys (bh-ebp-110-4) bound as `:key`, not credentials",
    ),
    (
        "apps/web/src/fixtures/seed/standards.ts",
        "SECRET-003",
        "K-02-T13: firm standard keys (bh-tax-02), the standards' identifiers, not credentials",
    ),
    (
        "docs/design/parity-manifest.json",
        "PII-003",
        "SHA-256 digests of handoff screenshots: a hex digest can hold a Luhn-valid run of"
        " digits, never a card number",
    ),
    (
        "apps/web/src/fixtures/contracts/review-grammar.test.ts",
        "SECRET-003",
        "C3 `field_key` values are tax-form line codes (f1040.l2a), not credentials",
    ),
    (
        "apps/web/src/fixtures/seed/review.ts",
        "SECRET-003",
        "P-04-T34: the C3 frames moved from review-grammar.test.ts; `field_key` values are"
        " tax-form line codes (f1040.l2a, sch_b.p1.l1.halvard), not credentials",
    ),
    (
        "apps/web/src/fixtures/scenarios/POR-01.ts",
        "SECRET-003",
        "POR-01e's reminder-link fragment is a readable fixture word, not a 256-bit link token",
    ),
    (
        "apps/web/src/fixtures/seed/client-records.ts",
        "SECRET-003",
        "CLI-02 overview items carry a `key` row code (form_7004.filed), never a credential",
    ),
    (
        "apps/web/src/fixtures/seed/engine-sync.ts",
        "SECRET-003",
        "T-01-T15: TAX-09 diagnostics carry a `field_key` tax-form line code (f8995a.ubia),"
        " not credentials",
    ),
    (
        "apps/web/src/fixtures/seed/reference-sets.ts",
        "SECRET-003",
        "K-02-T17: C21 reference sets carry a `key` / `set_key` set code"
        " (us.due_date_rules.ty2025), never a credential",
    ),
)
DATA_SUFFIXES = frozenset({".csv", ".json", ".yaml", ".yml", ".txt", ".tsv"})
CONFIG_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".yaml", ".yml", ".toml"}
    | {".sh", ".ini", ".cfg"}
)
BARE_SUFFIXES = frozenset({".yaml", ".yml", ".sh", ".ini", ".cfg"})


@dataclass(frozen=True)
class TextFile:
    rel: str
    lines: list[str]

    @property
    def suffix(self) -> str:
        return PurePosixPath(self.rel).suffix.lower()

    @property
    def is_env(self) -> bool:
        name = PurePosixPath(self.rel).name.lower()
        return name.startswith(".env") or name.endswith(".env") or name == "dockerfile"


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    adr: str
    check: Callable[[TextFile], Iterator[Finding]]


# --- SECRET-001 private keys ------------------------------------------------------------------

_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")


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
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{34}\b")),
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
    rf"(?i)^\s*(?:export\s+|ENV\s+|-\s+)?{_CRED_NAME}\s*[:=]\s*(?P<value>[^\s\"'#]+)\s*(?:#.*)?$"
)
_ENV_DEFAULT = re.compile(
    rf"(?i)(?:getenv|environ\.get)\(\s*([\"']){_CRED_NAME}\1\s*,\s*([\"'])(?P<value>[^\"']*)\2"
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
    tokens = [t for t in re.split(r"[^a-z0-9]+", value.lower()) if t]
    return (
        not value
        or value.startswith(("<", "${", "{{", "$"))
        or len(set(value)) == 1
        or any(t.startswith(word) for t in tokens for word in _PLACEHOLDER_WORDS)
    )


def _is_credential(value: str) -> bool:
    return (
        len(value) >= 8
        and not any(c.isspace() for c in value)
        and "/" not in value
        and ":" not in value
        and any(c.isalpha() for c in value)
        and any(c.isdigit() for c in value)
        and not _is_placeholder(value)
    )


def _check_credential_assignment(f: TextFile) -> Iterator[Finding]:
    if not f.is_env and f.suffix not in CONFIG_SUFFIXES:
        return
    bare_allowed = f.is_env or f.suffix in BARE_SUFFIXES
    for n, line in enumerate(f.lines, start=1):
        quoted = [m.group("value") for m in _QUOTED.finditer(line)]
        quoted += [m.group("value") for m in _ENV_DEFAULT.finditer(line)]
        bare = _BARE.match(line) if bare_allowed else None
        values = quoted + ([bare.group("value")] if bare else [])
        if any(_is_credential(v) for v in values):
            yield Finding(n, "credential assigned to a key/secret/token/password name")


# --- SECRET-004 credentials in URLs ----------------------------------------------------------

_URL_CREDENTIALS = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:(?P<password>[^\s@/]+)@")


def _check_url_credentials(f: TextFile) -> Iterator[Finding]:
    for n, line in enumerate(f.lines, start=1):
        if any(_is_credential(m.group("password")) for m in _URL_CREDENTIALS.finditer(line)):
            yield Finding(n, "credentials embedded in a URL")


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
    Rule("SECRET-004", "Credentials embedded in URLs", "ADR-083", _check_url_credentials),
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


# History only: old blobs reviewed by hand and found not to be secrets (blob id -> reason). Pinned
# by blob, so a new secret at the same path is still reported.
REVIEWED_BLOBS: dict[str, str] = {
    "3fbf56df9da9ba9087c8e8e0eefe205f34e85379": "config.py: local_master_key placeholder",
    "7e0c27c59f843359ca7ecc3ed453a9b5cbd2792c": "config.py: local_master_key placeholder",
    "56b5f952f4141ddbdd84c2e498a2d32cd8dbeaf4": "payload_codec.py: key id platform-v1, a name",
    "0128c3fbde75fea0ed1c15025440167cec52434b": "test_payload_codec.py: key id platform-v1",
    "ff89ffd90c46be1227a02efeb40c3877bb92e2ed": "test_evidence.py: date-stamped file names",
    "c6f3a44ea50f494f2cad51b35daf45d0543d0143": "trial balance test: all-zero account number",
    "bbdfc8d0ce3d4da90297e2397cd9b53c527b9b9a": "Q-02.md: example SSN in a masking example",
}


def _allowed(rel: str, rule_id: str) -> bool:
    return any(fnmatch(rel, g) and fnmatch(rule_id, r) for g, r, _ in ALLOW)


def _decode(rel: str, data: bytes) -> TextFile | None:
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return TextFile(rel, data.decode("utf-16", errors="replace").splitlines())
    if b"\0" in data:
        return None
    return TextFile(rel, data.decode("utf-8", errors="replace").splitlines())


def _load(repo: Path, rel: str) -> TextFile | None:
    if PurePosixPath(rel).name in LOCKFILES or any(fnmatch(rel, g) for g in EXCLUDE):
        return None
    path = repo / rel
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        return None
    return _decode(rel, path.read_bytes())


def scan(repo: Path = REPO, files: Iterable[str] | None = None) -> list[Violation]:
    violations: list[Violation] = []
    for rel in _tracked_files(repo) if files is None else files:
        text = _load(repo, rel)
        if text is None:
            continue
        for rule in RULES:
            for f in rule.check(text):
                if not _allowed(rel, rule.id):
                    violations.append(Violation(rel, f.line, rule.id, f.message, rule.adr))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule_id))


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to scan history")
    return subprocess.run(
        [git, *args], cwd=repo, input=stdin, capture_output=True, check=True
    ).stdout


def _history_blobs(repo: Path) -> dict[str, str]:
    """Blob id -> one path it was committed at, for every blob reachable from any ref."""
    blobs: dict[str, str] = {}
    for line in _git(repo, "rev-list", "--objects", "--all").decode().splitlines():
        sha, _, rel = line.partition(" ")
        if rel and sha not in blobs:
            blobs[sha] = rel
    if not blobs:
        return {}
    checked = _git(repo, "cat-file", "--batch-check", stdin="\n".join(blobs).encode() + b"\n")
    keep: dict[str, str] = {}
    for row in checked.decode().splitlines():
        sha, kind, size = row.split()
        if kind == "blob" and int(size) <= MAX_BYTES:
            keep[sha] = blobs[sha]
    return keep


def _first_commit(repo: Path, sha: str) -> str:
    out = _git(repo, "log", "--all", "--reverse", "--format=%h", f"--find-object={sha}")
    return (out.decode().split() or ["unknown"])[0]


def scan_history(repo: Path = REPO) -> list[Violation]:
    violations: list[Violation] = []
    for sha, rel in _history_blobs(repo).items():
        if sha in REVIEWED_BLOBS:
            continue
        name = PurePosixPath(rel).name
        if name in LOCKFILES or any(fnmatch(rel, g) for g in EXCLUDE):
            continue
        text = _decode(rel, _git(repo, "cat-file", "blob", sha))
        if text is None:
            continue
        hits = [
            (rule, f) for rule in RULES for f in rule.check(text) if not _allowed(rel, rule.id)
        ]
        if not hits:
            continue
        commit = _first_commit(repo, sha)
        for rule, f in hits:
            message = f"{f.message} (first in commit {commit}, blob {sha[:12]})"
            violations.append(Violation(rel, f.line, rule.id, message, rule.adr))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule_id, v.message))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    violations = scan_history() if "--history" in args else scan()
    for v in violations:
        print(v)
    if violations:
        print(f"{len(violations)} secret or identifier finding(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
