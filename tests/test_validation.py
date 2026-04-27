"""Validate that all gsyan888 known bugs are detected and fixed."""
import pytest

from stroke_order.validation import (
    KNOWN_BUGS,
    apply_known_bug_fix,
    validate_character,
)


@pytest.mark.parametrize("hex_code,expected_count", [
    (hex_code, exp) for hex_code, (exp, _, _) in KNOWN_BUGS.items()
])
def test_known_bug_detected_and_fixed(source, hex_code, expected_count):
    char = chr(int(hex_code, 16))
    try:
        c = source.get_character(char)
    except Exception:
        pytest.skip(f"fixture missing for U+{hex_code}")

    # Before fix: validation should flag as invalid + fixable
    r = validate_character(c)
    assert not r.is_valid, f"{char}: expected known-bug detection to fail validation"
    assert r.fixable, f"{char}: expected the bug to be auto-fixable"

    # After fix: should have correct stroke count
    fixed, did_fix = apply_known_bug_fix(c)
    assert did_fix
    assert fixed.stroke_count == expected_count
    assert any("auto-fix" in n for n in fixed.validation_notes)


def test_healthy_char_passes(source):
    c = source.get_character("永")
    r = validate_character(c)
    assert r.is_valid
    assert not r.fixable  # nothing to fix


def test_apply_fix_idempotent_on_healthy(source):
    c = source.get_character("永")
    fixed, did_fix = apply_known_bug_fix(c)
    assert not did_fix
    assert fixed is c  # returns same object
