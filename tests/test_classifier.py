import math

from stroke_order.classifier import (
    classify_character,
    classify_stroke,
    detect_hook,
)
from stroke_order.ir import Point, Stroke


def _stroke(points: list[tuple[float, float]]) -> Stroke:
    return Stroke(index=0, raw_track=[Point(x, y) for x, y in points], outline=[])


def test_classify_horizontal_long():
    s = _stroke([(100, 500), (1900, 500)])  # horizontal right
    assert classify_stroke(s) == 2  # 橫


def test_classify_vertical_long():
    s = _stroke([(500, 100), (500, 1900)])  # vertical down
    assert classify_stroke(s) == 1  # 豎


def test_classify_pie_long():
    s = _stroke([(1500, 300), (500, 1300)])  # diagonal down-left
    assert classify_stroke(s) == 7  # 撇


def test_classify_na_long():
    s = _stroke([(500, 300), (1500, 1300)])  # diagonal down-right
    assert classify_stroke(s) == 8  # 捺


def test_classify_short_dot_right():
    s = _stroke([(500, 500), (600, 600)])  # short, down-right
    assert classify_stroke(s) == 4  # 橫點


def test_classify_short_dot_left():
    s = _stroke([(600, 500), (500, 600)])  # short, down-left
    assert classify_stroke(s) == 3  # 豎點


def test_detect_hook_true():
    # hook = last segment reverses overall direction
    points = [Point(0, 0), Point(100, 0), Point(200, 0), Point(180, -30)]
    assert detect_hook(points)


def test_detect_hook_false_for_straight():
    assert not detect_hook([Point(0, 0), Point(100, 0), Point(200, 0)])


def test_classify_character_on_yong(source):
    """永 should have recognizable 5-stroke classification."""
    c = source.get_character("永")
    classify_character(c)
    assert len(c.signature) == 5
    # first stroke is the top dot (點/點-like)
    assert c.strokes[0].kind_code in (3, 4)
    # second stroke is 橫折鉤 (should classify as 5 or 6, not 1/2/7/8)
    assert c.strokes[1].kind_code in (5, 6)
    # stroke 2 of 永 has hook (MOE animation)
    assert c.strokes[1].has_hook
