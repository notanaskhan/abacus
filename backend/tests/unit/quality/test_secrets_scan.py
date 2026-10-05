"""AC-20: the secrets and real-identifier scan flags each violation and passes clean files.

The scanner runs over this repository, so no test input is written as a literal here: tokens,
identifiers and check digits are assembled at runtime.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp
from abacus_tools.quality import secrets_scan as ss

REPO = Path(__file__).resolve().parents[4]


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _scan(root: Path, rel: str, text: str) -> list[ss.Violation]:
    _write(root, rel, text)
    return ss.scan(root, files=[rel])


def _rule_ids(root: Path, rel: str, text: str) -> list[str]:
    return [v.rule_id for v in _scan(root, rel, text)]


# --- runtime builders ------------------------------------------------------------------------


def _luhn_complete(body: str) -> str:
    """Append the Luhn check digit to a digit string."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return body + str((10 - total % 10) % 10)


def _break_last_digit(number: str) -> str:
    last = (int(number[-1]) + 1) % 10
    return number[:-1] + str(last)


def _card(length: int) -> str:
    body = ("40000012345678901234"[: length - 1]).ljust(length - 1, "7")
    return _luhn_complete(body)


def _aba() -> str:
    body = "".join(["0110", "0002"])
    weights = [3, 7, 1, 3, 7, 1, 3, 7]
    total = sum(w * int(d) for w, d in zip(weights, body, strict=True))
    return body + str((10 - total % 10) % 10)


def _ssn(area: str, group: str, serial: str) -> str:
    return "-".join([area, group, serial])


def _ein(prefix: str) -> str:
    return prefix + "-" + "3456789"


def _assign(name: str, value: str, *, quote: str = '"', sep: str = " = ") -> str:
    return name + sep + quote + value + quote + "\n"


PRIVATE_KEY_LABELS = ["RSA PRIVATE KEY", "EC PRIVATE KEY", "OPENSSH PRIVATE KEY", "PRIVATE KEY"]


def _pem_header(label: str) -> str:
    return "-----" + "BEGIN " + label + "-----"


# (provider prefix, body alphabet unit, body length)
def _token_bodies() -> list[tuple[str, str]]:
    return [
        ("aws-akia", "AKIA" + "Q" * 16),
        ("aws-asia", "ASIA" + "7" * 16),
        ("gh-ghp", "ghp_" + "a1" * 18),
        ("gh-gho", "gho_" + "Zz" * 18),
        ("gh-ghu", "ghu_" + "9" * 36),
        ("gh-ghs", "ghs_" + "b" * 36),
        ("gh-ghr", "ghr_" + "c3" * 18),
        ("gh-pat", "github_pat_" + "A_" * 11),
        ("anthropic", "sk-" + "ant-" + "a-" * 10),
        ("openai-proj", "sk-" + "proj-" + "b_" * 10),
        ("openai-legacy", "sk-" + "aB3" * 16),
        ("slack-b", "xox" + "b-" + "1" * 10),
        ("slack-p", "xox" + "p-" + "1-2-3-4-5-6"),
        ("stripe", "sk_" + "live_" + "z9" * 8),
        ("google", "AIza" + ("Ab_" * 12)[:35]),
    ]


def _short_tokens() -> list[tuple[str, str]]:
    return [
        ("aws-short", "AKIA" + "Q" * 15),
        ("aws-lowercase", "akia" + "q" * 16),
        ("gh-short", "ghp_" + "a" * 35),
        ("gh-pat-short", "github_pat_" + "A" * 21),
        ("anthropic-short", "sk-" + "ant-" + "a" * 19),
        ("openai-legacy-short", "sk-" + "a" * 47),
        ("slack-bad-letter", "xox" + "z-" + "1" * 10),
        ("slack-short", "xox" + "b-" + "1" * 9),
        ("stripe-short", "sk_" + "live_" + "z" * 15),
        ("google-short", "AIza" + "A" * 34),
    ]


# --- SECRET-001 -------------------------------------------------------------------------------


@pytest.mark.parametrize("label", PRIVATE_KEY_LABELS)
def test_ac20_secret_001_flags_violation(tmp_path: Path, label: str) -> None:
    text = "line one\n" + _pem_header(label) + "\nbody\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, "keys/id.txt", text)] == [
        ("SECRET-001", 2)
    ]


@pytest.mark.parametrize(
    "header",
    [
        _pem_header("CERTIFICATE"),
        _pem_header("PUBLIC KEY"),
        "-----" + "END " + "RSA PRIVATE KEY" + "-----",
        "BEGIN " + "PRIVATE KEY" + " without dashes",
    ],
    ids=["certificate", "public-key", "end-marker", "no-dashes"],
)
def test_ac20_secret_001_allows_clean(tmp_path: Path, header: str) -> None:
    assert _rule_ids(tmp_path, "keys/cert.txt", header + "\nbody\n") == []


# --- SECRET-002 -------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "token"), _token_bodies(), ids=[n for n, _ in _token_bodies()])
def test_ac20_secret_002_flags_violation(tmp_path: Path, name: str, token: str) -> None:
    text = "first\nsee " + token + " here\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, "notes/a.md", text)] == [
        ("SECRET-002", 2)
    ]


@pytest.mark.parametrize(("name", "token"), _short_tokens(), ids=[n for n, _ in _short_tokens()])
def test_ac20_secret_002_allows_clean(tmp_path: Path, name: str, token: str) -> None:
    assert _rule_ids(tmp_path, "notes/a.md", "see " + token + " here\n") == []


# --- SECRET-003 -------------------------------------------------------------------------------

REAL_LOOKING = "Hq7rTn4Vb8Lw"

# (relative path, content) for non-placeholder assignments
SECRET_003_VIOLATIONS: list[tuple[str, str]] = [
    ("src/cfg.py", _assign("API_KEY", REAL_LOOKING)),
    ("src/cfg.py", _assign("client_secret", REAL_LOOKING, quote="'")),
    ("src/cfg.py", _assign("GITHUB_TOKEN", REAL_LOOKING, sep="=")),
    ("src/cfg.py", _assign("DB_PASSWORD", REAL_LOOKING)),
    ("src/cfg.py", _assign("db_passwd", REAL_LOOKING)),
    ("apps/web/src/cfg.ts", "export const " + _assign("API_KEY", REAL_LOOKING).rstrip() + ";\n"),
    ("deploy/values.yaml", _assign("api_key", REAL_LOOKING, quote="", sep=": ")),
    ("deploy/values.yaml", _assign("api_key", REAL_LOOKING, sep=": ")),
    ("pyproject.toml", _assign("secret", REAL_LOOKING)),
    (".env", _assign("SESSION_SECRET", REAL_LOOKING, quote="", sep="=")),
    ("config/.env.production", _assign("AUTH_TOKEN", REAL_LOOKING, quote="", sep="=")),
    ("config/settings.json", '  "' + _assign("API_KEY", REAL_LOOKING, sep='": ').rstrip() + "\n"),
]

SECRET_003_CLEAN: list[tuple[str, str]] = [
    ("src/cfg.py", _assign("API_KEY", "")),
    ("src/cfg.py", _assign("API_KEY", "<your-key-here>")),
    ("src/cfg.py", _assign("API_KEY", "${API_KEY_FROM_ENV}")),
    ("src/cfg.py", _assign("API_KEY", "{{ vault.api_key }}")),
    ("src/cfg.py", _assign("API_KEY", "$SOME_ENV_VALUE")),
    ("src/cfg.py", _assign("API_KEY", "changeme-please")),
    ("src/cfg.py", _assign("API_KEY", "CHANGEME")),
    ("src/cfg.py", _assign("API_KEY", "my-Example-key")),
    ("src/cfg.py", _assign("API_KEY", "placeholder-value")),
    ("src/cfg.py", _assign("DB_PASSWORD", "dummy-pass1")),
    ("src/cfg.py", _assign("GITHUB_TOKEN", "fake-token-123")),
    ("src/cfg.py", _assign("DB_PASSWORD", "my-test-pass1")),
    ("src/cfg.py", _assign("API_KEY", "xxx-aaaa-bbb")),
    ("src/cfg.py", _assign("API_KEY", "REDACTED-value")),
    ("src/cfg.py", _assign("API_KEY", "a" * 10)),
    ("src/cfg.py", _assign("API_KEY", "9" * 12)),
    ("src/cfg.py", _assign("API_KEY", "short")),
    ("src/cfg.py", _assign("API_KEY", "has some spaces inside")),
    ("src/cfg.py", _assign("PAGE_SIZE", REAL_LOOKING)),
    ("src/cfg.py", "API_KEY = os.environ.get(NAME)\n"),
    ("src/cfg.py", "API_KEY: str\n"),
    ("deploy/values.yaml", _assign("api_key", "<set-me>", quote="", sep=": ")),
    ("deploy/values.yaml", _assign("api_key", "", quote="", sep=": ")),
    (".env", _assign("SESSION_SECRET", "changeme", quote="", sep="=")),
    (".env.example", _assign("AUTH_TOKEN", "${AUTH_TOKEN}", quote="", sep="=")),
    ("README.md", _assign("API_KEY", REAL_LOOKING)),
]


@pytest.mark.parametrize(("rel", "text"), SECRET_003_VIOLATIONS)
def test_ac20_secret_003_flags_violation(tmp_path: Path, rel: str, text: str) -> None:
    assert _rule_ids(tmp_path, rel, text) == ["SECRET-003"]


@pytest.mark.parametrize(("rel", "text"), SECRET_003_CLEAN)
def test_ac20_secret_003_allows_clean(tmp_path: Path, rel: str, text: str) -> None:
    assert _rule_ids(tmp_path, rel, text) == []


# --- PII-001 ----------------------------------------------------------------------------------

SSN_VIOLATIONS = [
    ("123", "45", "6789"),
    ("001", "01", "0001"),
    ("665", "12", "3456"),
    ("667", "12", "3456"),
    ("899", "99", "9999"),
]
SSN_CLEAN = [
    ("000", "12", "3456"),
    ("666", "12", "3456"),
    ("900", "12", "3456"),
    ("987", "65", "4321"),
    ("999", "99", "9999"),
    ("123", "00", "4567"),
    ("123", "45", "0000"),
]


@pytest.mark.parametrize("parts", SSN_VIOLATIONS)
@pytest.mark.parametrize("rel", ["src/a.py", "docs/a.md", "data/a.csv"])
def test_ac20_pii_001_flags_violation(
    tmp_path: Path, parts: tuple[str, str, str], rel: str
) -> None:
    text = "first\nssn " + _ssn(*parts) + " end\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, rel, text)] == [("PII-001", 2)]


@pytest.mark.parametrize("parts", SSN_CLEAN)
def test_ac20_pii_001_allows_reserved_ranges(tmp_path: Path, parts: tuple[str, str, str]) -> None:
    assert _rule_ids(tmp_path, "data/a.csv", "ssn " + _ssn(*parts) + " end\n") == []


@pytest.mark.parametrize(
    "text",
    ["1" + _ssn("234", "56", "7890"), _ssn("123", "45", "6789") + "0", "12-34-5678"],
    ids=["leading-digit", "trailing-digit", "wrong-shape"],
)
def test_ac20_pii_001_requires_word_boundaries(tmp_path: Path, text: str) -> None:
    assert _rule_ids(tmp_path, "src/a.py", text + "\n") == []


# --- PII-002 ----------------------------------------------------------------------------------

EIN_VALID_PREFIXES = [
    "01", "06", "10", "16", "20", "27", "30", "48", "50", "68", "71", "77", "80", "88", "90",
    "95", "98", "99",
]  # fmt: skip
EIN_INVALID_PREFIXES = [
    "00", "07", "08", "09", "17", "18", "19", "28", "29", "49", "69", "70", "78", "79", "89",
    "96", "97",
]  # fmt: skip
EIN_DATA_FILES = ["a.csv", "a.json", "a.yaml", "a.yml", "a.txt", "a.tsv"]
EIN_CODE_FILES = ["a.py", "a.md", "a.ts", "a.toml"]


@pytest.mark.parametrize("prefix", EIN_VALID_PREFIXES)
def test_ac20_pii_002_flags_violation(tmp_path: Path, prefix: str) -> None:
    text = "first\nein " + _ein(prefix) + " end\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, "data/a.csv", text)] == [("PII-002", 2)]


@pytest.mark.parametrize("rel", EIN_DATA_FILES)
def test_ac20_pii_002_flags_data_like_files(tmp_path: Path, rel: str) -> None:
    assert _rule_ids(tmp_path, "data/" + rel, "ein " + _ein("12") + "\n") == ["PII-002"]


@pytest.mark.parametrize("prefix", EIN_INVALID_PREFIXES)
def test_ac20_pii_002_allows_unassigned_prefix(tmp_path: Path, prefix: str) -> None:
    assert _rule_ids(tmp_path, "data/a.csv", "ein " + _ein(prefix) + "\n") == []


@pytest.mark.parametrize("rel", EIN_CODE_FILES)
def test_ac20_pii_002_allows_code_like_files(tmp_path: Path, rel: str) -> None:
    assert _rule_ids(tmp_path, "src/" + rel, "ein " + _ein("12") + "\n") == []


# --- PII-003 ----------------------------------------------------------------------------------


def _grouped(number: str, sep: str) -> str:
    return sep.join(number[i : i + 4] for i in range(0, len(number), 4))


@pytest.mark.parametrize("length", [13, 15, 16, 19])
def test_ac20_pii_003_flags_luhn_valid_card(tmp_path: Path, length: int) -> None:
    text = "first\ncard " + _card(length) + " end\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, "src/a.py", text)] == [("PII-003", 2)]


@pytest.mark.parametrize("sep", [" ", "-"])
def test_ac20_pii_003_flags_grouped_card(tmp_path: Path, sep: str) -> None:
    text = "card " + _grouped(_card(16), sep) + " end\n"
    assert _rule_ids(tmp_path, "src/a.py", text) == ["PII-003"]


@pytest.mark.parametrize("length", [13, 16, 19])
def test_ac20_pii_003_allows_luhn_invalid_number(tmp_path: Path, length: int) -> None:
    text = "card " + _break_last_digit(_card(length)) + " end\n"
    assert _rule_ids(tmp_path, "src/a.py", text) == []


@pytest.mark.parametrize(
    "number",
    [
        "".join(["4111", "1111", "1111", "1111"]),
        "".join(["4242", "4242", "4242", "4242"]),
        "".join(["5555", "5555", "5555", "4444"]),
        "".join(["5105", "1051", "0510", "5100"]),
        "".join(["378282", "246310", "005"]),
        "".join(["371449", "635398", "431"]),
        "".join(["6011", "1111", "1111", "1117"]),
        "".join(["3530", "1113", "3330", "0000"]),
    ],
    ids=["visa", "visa-2", "mc", "mc-2", "amex", "amex-2", "discover", "jcb"],
)
def test_ac20_pii_003_allows_published_test_cards(tmp_path: Path, number: str) -> None:
    assert _rule_ids(tmp_path, "src/a.py", "card " + number + " end\n") == []


def test_ac20_pii_003_allows_spaced_published_test_card(tmp_path: Path) -> None:
    number = _grouped("".join(["4111", "1111", "1111", "1111"]), " ")
    assert _rule_ids(tmp_path, "src/a.py", "card " + number + " end\n") == []


@pytest.mark.parametrize("label", ["routing", "ROUTING number", "Aba", "aba:"])
def test_ac20_pii_003_flags_labelled_aba(tmp_path: Path, label: str) -> None:
    text = "first\n" + label + " " + _aba() + "\n"
    assert [(v.rule_id, v.line) for v in _scan(tmp_path, "data/a.txt", text)] == [("PII-003", 2)]


def test_ac20_pii_003_allows_unlabelled_aba(tmp_path: Path) -> None:
    assert _rule_ids(tmp_path, "data/a.txt", "number " + _aba() + "\n") == []


def test_ac20_pii_003_allows_labelled_number_failing_checksum(tmp_path: Path) -> None:
    text = "routing " + _break_last_digit(_aba()) + "\n"
    assert _rule_ids(tmp_path, "data/a.txt", text) == []


# --- messages never leak the value ------------------------------------------------------------


def _leak_cases() -> list[tuple[str, str, str, str]]:
    return [
        ("SECRET-002", "aws", "notes/a.md", "AKIA" + "Q" * 16),
        ("SECRET-002", "github", "notes/a.md", "ghp_" + "a1" * 18),
        ("SECRET-003", "assignment", "src/cfg.py", REAL_LOOKING),
        ("PII-001", "ssn", "src/a.py", _ssn("123", "45", "6789")),
        ("PII-002", "ein", "data/a.csv", _ein("12")),
        ("PII-003", "card", "src/a.py", _card(16)),
        ("PII-003", "aba", "data/a.txt", _aba()),
    ]


@pytest.mark.parametrize(
    ("rule_id", "_name", "rel", "value"), _leak_cases(), ids=[c[1] for c in _leak_cases()]
)
def test_ac20_messages_never_contain_the_matched_value(
    tmp_path: Path, rule_id: str, _name: str, rel: str, value: str
) -> None:
    if rule_id == "SECRET-003":
        text = _assign("API_KEY", value)
    elif _name == "aba":
        text = "routing " + value + "\n"
    else:
        text = "value " + value + " end\n"
    [violation] = _scan(tmp_path, rel, text)
    assert violation.rule_id == rule_id
    assert value not in violation.message
    assert value not in str(violation)


# --- skipped files ----------------------------------------------------------------------------

_TOKEN = "AKIA" + "Q" * 16


@pytest.mark.parametrize("rel", ["uv.lock", "pnpm-lock.yaml", "backend/uv.lock"])
def test_ac20_lockfiles_are_skipped(tmp_path: Path, rel: str) -> None:
    assert _rule_ids(tmp_path, rel, "hash " + _TOKEN + "\n") == []


def test_ac20_nul_byte_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "blob.bin").write_bytes(b"\x00" + _TOKEN.encode() + b"\n")
    assert ss.scan(tmp_path, files=["blob.bin"]) == []


def test_ac20_file_over_one_megabyte_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text(_TOKEN + "\n" + "a" * 2_000_000, encoding="utf-8")
    assert ss.scan(tmp_path, files=["big.txt"]) == []


def test_ac20_missing_file_is_skipped(tmp_path: Path) -> None:
    assert ss.scan(tmp_path, files=["does/not/exist.txt"]) == []


def test_ac20_exclude_globs_skip_matching_paths_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ss, "EXCLUDE", ("fixtures/*",))
    _write(tmp_path, "fixtures/a.txt", _TOKEN + "\n")
    _write(tmp_path, "other/a.txt", _TOKEN + "\n")
    found = ss.scan(tmp_path, files=["fixtures/a.txt", "other/a.txt"])
    assert [(v.path, v.rule_id) for v in found] == [("other/a.txt", "SECRET-002")]


# --- files argument, ordering, output ---------------------------------------------------------


def test_ac20_only_listed_files_are_scanned(tmp_path: Path) -> None:
    _write(tmp_path, "listed.txt", "clean\n")
    _write(tmp_path, "unlisted.txt", _TOKEN + "\n")
    assert ss.scan(tmp_path, files=["listed.txt"]) == []


def test_ac20_empty_files_list_scans_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "unlisted.txt", _TOKEN + "\n")
    assert ss.scan(tmp_path, files=[]) == []


def test_ac20_violations_are_sorted_by_path_line_rule(tmp_path: Path) -> None:
    ssn = _ssn("123", "45", "6789")
    _write(tmp_path, "b.txt", "x\n" + _TOKEN + "\n")
    _write(tmp_path, "a.txt", "x\nx\n" + ssn + "\n" + _TOKEN + "\n")
    _write(tmp_path, "c.txt", _TOKEN + "\n")
    found = ss.scan(tmp_path, files=["c.txt", "b.txt", "a.txt"])
    assert [(v.path, v.line, v.rule_id) for v in found] == [
        ("a.txt", 3, "PII-001"),
        ("a.txt", 4, "SECRET-002"),
        ("b.txt", 2, "SECRET-002"),
        ("c.txt", 1, "SECRET-002"),
    ]


def test_ac20_violation_is_the_banned_patterns_type() -> None:
    assert ss.Violation is bp.Violation


@pytest.mark.parametrize(
    ("text", "rule_id", "adr"),
    [
        ("see " + _TOKEN + "\n", "SECRET-002", "ADR-083"),
        ("see " + _ssn("123", "45", "6789") + "\n", "PII-001", "ADR-085"),
    ],
)
def test_ac20_violation_output_names_path_line_rule_and_adr(
    tmp_path: Path, text: str, rule_id: str, adr: str
) -> None:
    [violation] = _scan(tmp_path, "docs/n.txt", "\n" + text)
    pattern = rf"docs/n\.txt:2: {rule_id} \S.* \({adr}\)"
    assert re.fullmatch(pattern, str(violation))


# --- main -------------------------------------------------------------------------------------


def test_ac20_main_prints_violations_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    found = [ss.Violation("a.txt", 1, "SECRET-002", "message", "ADR-083")]

    def fake_scan(*_args: object, **_kwargs: object) -> list[ss.Violation]:
        return found

    monkeypatch.setattr(ss, "scan", fake_scan)
    assert ss.main() == 1
    assert capsys.readouterr().out == "a.txt:1: SECRET-002 message (ADR-083)\n"


def test_ac20_main_exits_0_when_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty: list[ss.Violation] = []

    def fake_scan(*_args: object, **_kwargs: object) -> list[ss.Violation]:
        return empty

    monkeypatch.setattr(ss, "scan", fake_scan)
    assert ss.main() == 0
    assert capsys.readouterr().out == ""


def test_ac20_repository_has_no_secrets() -> None:
    # Deliberately depends on live repo state: this is the AC-20 claim itself, and duplicates
    # the secrets step of `make check-fast`.
    assert ss.scan(REPO) == []
