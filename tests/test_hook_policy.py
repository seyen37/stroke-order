"""Hook policy tests: static mode should trim terminal hooks."""
from stroke_order.classifier import classify_character
from stroke_order.hook_policy import apply_hook_policy
from stroke_order.ir import Point, Stroke


def test_animation_is_noop(source):
    c = source.get_character("永")
    classify_character(c)
    original_counts = [len(s.raw_track) for s in c.strokes]
    apply_hook_policy(c, "animation")
    assert [len(s.raw_track) for s in c.strokes] == original_counts


def test_static_strips_hook_from_ri(source):
    """日's 2nd stroke has a hook in g0v/MOE animation data."""
    c = source.get_character("日")
    classify_character(c)
    stroke_2 = c.strokes[1]
    assert stroke_2.has_hook, "precondition: 日's stroke 2 must have hook"
    before = len(stroke_2.raw_track)
    apply_hook_policy(c, "static")
    after = len(stroke_2.raw_track)
    assert after < before, "hook should have been trimmed"
    assert not stroke_2.has_hook


def test_static_leaves_nonhook_strokes_alone(source):
    """日's 1st stroke (豎) has no hook; static should not touch it."""
    c = source.get_character("日")
    classify_character(c)
    stroke_1 = c.strokes[0]
    assert not stroke_1.has_hook
    original_pts = list(stroke_1.raw_track)
    apply_hook_policy(c, "static")
    assert stroke_1.raw_track == original_pts


def test_unknown_policy_raises(source):
    c = source.get_character("永")
    import pytest
    with pytest.raises(ValueError, match="unknown hook policy"):
        apply_hook_policy(c, "silly")
