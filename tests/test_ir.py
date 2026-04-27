from stroke_order.ir import BBox, Character, EM_SIZE, Point, Stroke


def test_point_iter():
    p = Point(1, 2)
    assert tuple(p) == (1, 2)
    assert p.x == 1 and p.y == 2


def test_bbox_from_points():
    bb = BBox.from_points([Point(10, 20), Point(30, 5), Point(0, 100)])
    assert bb.x_min == 0 and bb.x_max == 30
    assert bb.y_min == 5 and bb.y_max == 100
    assert bb.width == 30 and bb.height == 95


def test_bbox_overflow_detection():
    assert BBox(-1, 0, 100, 100).overflows_em
    assert BBox(0, -1, 100, 100).overflows_em
    assert BBox(0, 0, EM_SIZE + 1, 100).overflows_em
    assert BBox(0, 0, 100, EM_SIZE + 1).overflows_em
    assert not BBox(0, 0, EM_SIZE, EM_SIZE).overflows_em
    assert not BBox(100, 100, 1000, 1000).overflows_em


def test_stroke_track_prefers_smoothed():
    raw = [Point(0, 0), Point(100, 100)]
    smoothed = [Point(0, 0), Point(50, 50), Point(100, 100)]
    s = Stroke(index=0, raw_track=raw, outline=[])
    assert s.track == raw  # no smoothed yet
    s.smoothed_track = smoothed
    assert s.track == smoothed


def test_character_signature_and_bbox():
    s1 = Stroke(index=0, raw_track=[Point(0, 0), Point(100, 0)], outline=[])
    s2 = Stroke(index=1, raw_track=[Point(0, 0), Point(0, 100)], outline=[])
    s1.kind_code = 2
    s2.kind_code = 1
    c = Character(char="X", unicode_hex="58", strokes=[s1, s2])
    assert c.signature == "21"
    assert c.stroke_count == 2
    bb = c.bbox
    assert bb.x_min == 0 and bb.x_max == 100
    assert bb.y_min == 0 and bb.y_max == 100
