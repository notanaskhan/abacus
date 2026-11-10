"""T-05-T07 (SPEC-651 AC-4.6, AC-4.2; ADR-237 §2): the closed formula grammar.

The parser accepts every formula the TXP-11 and TXP-02 specs show, rejects anything outside the
grammar with a code and a position, and nothing in the compute package can evaluate code.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.workpapers.compute import formula as f
from abacus_tools.quality import banned_patterns

COMPUTE = Path(f.__file__).parent


# --- the handoff's formulas -------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "=F18+G18+H18",  # TXP-02 a2: 01 Trial Balance!I18
        "=I18+J18",  # TXP-11 c
        "='06 Schedule K'!C31 \u00d7 25%",  # TXP-11 a: the expected value for 05 Capital!H12
        "='06 Schedule K'!C31 \u00d7 38%",  # TXP-07 a2: 05 Capital!H9
        "=D12+E12+F12+G12+H12+I12",  # 05 Capital crossfoot to J12
        "=SUM(J8:J12)",  # J13
        "=SUM(H8:H12)",  # the tax-exempt total, 6,200
        "=ROUND('06 Schedule K'!C31*0.25,0)",
        "=IF(J13=J15,0,J13-J15)",  # the difference row
        "=MIN(1,2)+MAX(A1:B2,3)",
        "=-(A1)",
        "=05!H12",  # a bare digit-led sheet key
        "=Capital!H12",
        "=$A$1+B$2",
        "=2319835*5/35",  # the Pell Street transfer, 331,405
        "=1550",
    ],
)
def test_ac4_6_the_handoff_formulas_parse(text: str) -> None:
    assert f.is_valid(text)


def test_cross_sheet_reference_keeps_the_quoted_title() -> None:
    parsed = f.parse("='06 Schedule K'!C31 \u00d7 25%")
    assert parsed.references == (f.CellRef("06 Schedule K", 3, 31),)
    assert parsed.tree == f.Binary(
        f.BinaryOp.MUL, f.CellRef("06 Schedule K", 3, 31), f.Percent(Decimal(25))
    )
    assert parsed.inputs("05 Capital") == ("'06 Schedule K'!C31",)
    assert f.render(parsed) == "='06 Schedule K'!C31*25%"


def test_inputs_are_canonical_addresses_in_first_seen_order() -> None:
    parsed = f.parse("=F18+G18+H18+F18")
    assert parsed.inputs("01 Trial Balance") == (
        "'01 Trial Balance'!F18",
        "'01 Trial Balance'!G18",
        "'01 Trial Balance'!H18",
    )


def test_a_range_expands_to_its_cells() -> None:
    parsed = f.parse("=SUM(H8:H12)")
    assert [ref.a1 for ref in parsed.references] == ["H8", "H9", "H10", "H11", "H12"]
    tree = parsed.tree
    assert isinstance(tree, f.Call) and tree.function is f.Function.SUM
    assert isinstance(tree.arguments[0], f.RangeRef)


def test_precedence_and_rendering_round_trip() -> None:
    for text in ("=A1+B1*C1", "=(A1+B1)*C1", "=A1-(B1-C1)", "=A1/(B1*C1)", "=-A1+2"):
        parsed = f.parse(text)
        assert f.parse(f.render(parsed)) == parsed


def test_operators_from_the_handoff_are_ascii_in_the_tree() -> None:
    assert f.parse("=A1 \u2212 B1 ÷ C1") == f.parse("=A1-B1/C1")
    assert f.parse("=IF(A1≥B1,1,0)") == f.parse("=IF(A1>=B1,1,0)")
    assert f.parse("=IF(A1≠B1,1,0)") == f.parse("=IF(A1<>B1,1,0)")


def test_column_letters_round_trip() -> None:
    for column in (1, 26, 27, 52, 702, 703, 16384):
        assert f.column_number(f.column_letters(column)) == column
    assert f.column_letters(16384) == "XFD"


# --- rejections with codes --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("=VLOOKUP(A1,B1:C9,2)", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ('=INDIRECT("A1")', f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=LOG10(A1)", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=NOW()", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ('=HYPERLINK("http://x")', f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=ROUND(A1)", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),  # wrong arity
        ("=IF(A1,1)", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=SUM()", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=XFE1", f.FormulaErrorCode.REF_INVALID),  # past the last column
        ("=A0", f.FormulaErrorCode.REF_INVALID),
        ("=A1048577", f.FormulaErrorCode.REF_INVALID),
        ("=''!A1", f.FormulaErrorCode.REF_INVALID),
        ("='unterminated!A1", f.FormulaErrorCode.REF_INVALID),
        ("=SUM(B9:A1)", f.FormulaErrorCode.REF_INVALID),  # reversed corners
        ("=SUM(A1:'Other'!B2)", f.FormulaErrorCode.REF_INVALID),  # across sheets
        ("='05 Capital'!(A1)", f.FormulaErrorCode.REF_INVALID),
        ("=A1:B2", f.FormulaErrorCode.TYPE),  # a range outside SUM/MIN/MAX
        ("=ROUND(A1:B2,0)", f.FormulaErrorCode.TYPE),
        ("=A1=B1", f.FormulaErrorCode.TYPE),  # a comparison outside IF
        ("=SUM(A1>B1)", f.FormulaErrorCode.TYPE),
        ("=A1%", f.FormulaErrorCode.TYPE),
        ("=", f.FormulaErrorCode.SYNTAX),
        ("", f.FormulaErrorCode.SYNTAX),
        ("=1+", f.FormulaErrorCode.SYNTAX),
        ("=(A1+B1", f.FormulaErrorCode.SYNTAX),
        ("=A1+B1)", f.FormulaErrorCode.SYNTAX),
        ('="text"', f.FormulaErrorCode.SYNTAX),  # no strings
        ("=A1&B1", f.FormulaErrorCode.SYNTAX),  # no concatenation
        ("=TRUE", f.FormulaErrorCode.SYNTAX),
        ("=__import__('os')", f.FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=[1]Sheet1!A1", f.FormulaErrorCode.SYNTAX),  # no external workbooks
        ("=A1 B1", f.FormulaErrorCode.SYNTAX),
    ],
)
def test_ac4_5_outside_the_grammar_is_refused_with_a_code(
    text: str, code: f.FormulaErrorCode
) -> None:
    with pytest.raises(f.FormulaError) as caught:
        f.parse(text)
    assert caught.value.code is code
    assert 0 <= caught.value.position <= len(text)


def test_the_error_carries_the_position_never_the_text() -> None:
    with pytest.raises(f.FormulaError) as caught:
        f.parse("=A1+VLOOKUP(secret)")
    assert caught.value.position == 4
    assert "secret" not in str(caught.value)
    assert "VLOOKUP" not in str(caught.value)


def test_nesting_and_length_are_bounded() -> None:
    with pytest.raises(f.FormulaError) as deep:
        f.parse("=" + "(" * 200 + "1" + ")" * 200)
    assert deep.value.code is f.FormulaErrorCode.SYNTAX
    with pytest.raises(f.FormulaError) as long:
        f.parse("=" + "+".join(["A1"] * 1500))
    assert long.value.code is f.FormulaErrorCode.SYNTAX


def test_the_evaluation_codes_are_declared() -> None:
    assert {c.value for c in f.FormulaErrorCode} >= {
        "ref_invalid",
        "cycle",
        "div_zero",
        "unsupported_function",
    }


# --- nothing evaluates code -------------------------------------------------------------------


def test_no_eval_in_the_compute_package() -> None:
    banned = {"eval", "exec", "compile", "__import__", "import_module", "literal_eval"}
    for path in COMPUTE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & banned, path.name


def test_formula_001_flags_eval_in_a_compute_package(tmp_path: Path) -> None:
    rule = next(r for r in banned_patterns.RULES if r.id == "FORMULA-001")
    assert isinstance(rule, banned_patterns.Rule)
    assert rule.applies_to("src/abacus/modules/workpapers/compute/formula.py")
    assert rule.applies_to("src/abacus/modules/tax/compute/entity/capital.py")
    assert not rule.applies_to("src/abacus/modules/workpapers/service.py")
    source = "def f(text):\n    return eval(text)\n"
    src = banned_patterns.SourceFile(
        "src/abacus/modules/workpapers/compute/bad.py",
        "abacus.modules.workpapers.compute.bad",
        ast.parse(source),
        {},
    )
    findings = list(rule.check(src))
    assert [finding.line for finding in findings] == [2]


def test_formula_001_passes_on_the_real_package() -> None:
    violations = [v for v in banned_patterns.scan() if v.rule_id == "FORMULA-001"]
    assert violations == []
