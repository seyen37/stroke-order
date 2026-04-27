"""Smoke tests for each exporter — exhaustive content validation is in
the end-to-end test (test_end_to_end.py)."""
import json
import xml.etree.ElementTree as ET

from stroke_order.classifier import classify_character
from stroke_order.exporters.gcode import GCodeOptions, character_to_gcode
from stroke_order.exporters.json_polyline import character_to_json
from stroke_order.exporters.svg import character_to_svg
from stroke_order.smoothing import smooth_character


def _prep(source):
    c = source.get_character("永")
    classify_character(c)
    smooth_character(c)
    return c


def test_svg_outline_parses_as_xml(source):
    c = _prep(source)
    svg = character_to_svg(c, mode="outline")
    root = ET.fromstring(svg)
    assert "svg" in root.tag
    # should have 5 outline paths
    paths = root.findall(".//{http://www.w3.org/2000/svg}path")
    assert len(paths) == 5


def test_svg_track_mode(source):
    c = _prep(source)
    svg = character_to_svg(c, mode="track")
    root = ET.fromstring(svg)
    polylines = root.findall(".//{http://www.w3.org/2000/svg}polyline")
    assert len(polylines) == 5


def test_svg_both_mode(source):
    c = _prep(source)
    svg = character_to_svg(c, mode="both", show_numbers=True, rainbow=True)
    root = ET.fromstring(svg)
    paths = root.findall(".//{http://www.w3.org/2000/svg}path")
    polylines = root.findall(".//{http://www.w3.org/2000/svg}polyline")
    texts = root.findall(".//{http://www.w3.org/2000/svg}text")
    assert len(paths) == 5      # outlines
    assert len(polylines) == 5  # tracks
    assert len(texts) == 5      # stroke numbers


def test_gcode_has_correct_pen_commands(source):
    c = _prep(source)
    gcode = character_to_gcode(c)
    lines = [l.strip() for l in gcode.split("\n") if l.strip()]
    pen_downs = sum(1 for l in lines if l.startswith("M3"))
    assert pen_downs == 5, f"expected 5 pen-down events, got {pen_downs}"
    # every stroke should be bracketed by pen up before and after
    assert gcode.count("M5") >= 6  # 5 per stroke + at least 1 start/end


def test_gcode_respects_char_size(source):
    c = _prep(source)
    opts_small = GCodeOptions(char_size_mm=10)
    opts_big = GCodeOptions(char_size_mm=40)
    g_small = character_to_gcode(c, opts_small)
    g_big = character_to_gcode(c, opts_big)
    # extract max X coord found in both
    import re
    def max_x(s):
        return max(float(m.group(1)) for m in re.finditer(r"X([-\d.]+)", s))
    assert max_x(g_big) > max_x(g_small) * 2


def test_json_roundtrip(source):
    c = _prep(source)
    blob = character_to_json(c)
    parsed = json.loads(blob)
    assert parsed["character"] == "永"
    assert parsed["unicode"] == "U+6C38"
    assert parsed["stroke_count"] == 5
    assert len(parsed["strokes"]) == 5
    for i, s in enumerate(parsed["strokes"]):
        assert s["index"] == i
        assert isinstance(s["track"], list)
        assert len(s["track"]) > 0
        assert s["kind_name"]  # non-empty
