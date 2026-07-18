"""5eu（架構健檢 W2）：篆/隸骨架幾何快取——合成 outline 免字型可測。"""
from __future__ import annotations

from copy import deepcopy

from stroke_order.ir import Character, Stroke
from stroke_order.sources import chongxi_seal as seal_mod
from stroke_order.sources import moe_lishu as lishu_mod


def _synthetic(data_source: str, char: str = "口") -> Character:
    # 粗橫槓 outline（EM 座標）——骨架化出一條水平中心線；
    # ⚠ 別用大實心方形：blob 骨架退化成點、walker 收不到 track
    outline = [
        {"type": "M", "x": 500, "y": 900},
        {"type": "L", "x": 1500, "y": 900},
        {"type": "L", "x": 1500, "y": 1100},
        {"type": "L", "x": 500, "y": 1100},
        {"type": "Z"},
    ]
    return Character(
        char=char,
        unicode_hex=f"{ord(char):x}",
        strokes=[Stroke(index=0, raw_track=[], outline=outline)],
        data_source=data_source,
    )


def test_seal_tracks_cached_and_objects_fresh():
    seal_mod._MODE_TRACKS_CACHE.clear()
    c = _synthetic("chongxi_seal")
    r1 = seal_mod.apply_seal_outline_mode(c, "skeleton")
    assert ("口", "skeleton") in seal_mod._MODE_TRACKS_CACHE
    r2 = seal_mod.apply_seal_outline_mode(deepcopy(c), "skeleton")
    # 幾何一致
    t1 = [[(p.x, p.y) for p in s.raw_track] for s in r1.strokes]
    t2 = [[(p.x, p.y) for p in s.raw_track] for s in r2.strokes]
    assert t1 == t2 and t1
    # 回傳物件必須是新的（無共享突變風險）
    assert r1 is not r2
    assert r1.strokes[0] is not r2.strokes[0]
    assert r1.strokes[0].raw_track[0] is not r2.strokes[0].raw_track[0]


def test_seal_cache_hit_skips_recompute(monkeypatch):
    seal_mod._MODE_TRACKS_CACHE.clear()
    calls = {"n": 0}
    import stroke_order.cns_skeleton as sk
    real = sk.outline_to_skeleton_tracks

    def spy(outline):
        calls["n"] += 1
        return real(outline)

    monkeypatch.setattr(sk, "outline_to_skeleton_tracks", spy)
    c = _synthetic("chongxi_seal", "永")
    seal_mod.apply_seal_outline_mode(c, "skeleton")
    seal_mod.apply_seal_outline_mode(c, "skeleton")
    assert calls["n"] == 1  # 第二次走快取，昂貴骨架化不重跑


def test_reset_singleton_clears_cache_and_bumps_bus():
    from stroke_order import cache_bus
    seal_mod._MODE_TRACKS_CACHE.clear()
    seal_mod.apply_seal_outline_mode(_synthetic("chongxi_seal"), "skeleton")
    assert seal_mod._MODE_TRACKS_CACHE
    before = cache_bus.epoch()
    seal_mod.reset_seal_singleton()
    assert not seal_mod._MODE_TRACKS_CACHE
    assert cache_bus.epoch() > before


def test_lishu_cache_same_contract():
    lishu_mod._MODE_TRACKS_CACHE.clear()
    c = _synthetic("moe_lishu")
    r1 = lishu_mod.apply_lishu_outline_mode(c, "skeleton")
    assert ("口", "skeleton") in lishu_mod._MODE_TRACKS_CACHE
    r2 = lishu_mod.apply_lishu_outline_mode(c, "skeleton")
    assert [len(s.raw_track) for s in r1.strokes] == [len(s.raw_track) for s in r2.strokes]
    before = len(lishu_mod._MODE_TRACKS_CACHE)
    lishu_mod.reset_lishu_singleton()
    assert len(lishu_mod._MODE_TRACKS_CACHE) < before or before == 0


def test_cache_capacity_bounded():
    seal_mod._MODE_TRACKS_CACHE.clear()
    old_max = seal_mod._MODE_TRACKS_CACHE_MAX
    try:
        seal_mod._MODE_TRACKS_CACHE_MAX = 3
        for i, ch in enumerate("甲乙丙丁戊"):
            seal_mod.apply_seal_outline_mode(_synthetic("chongxi_seal", ch), "skeleton")
        assert len(seal_mod._MODE_TRACKS_CACHE) <= 3
    finally:
        seal_mod._MODE_TRACKS_CACHE_MAX = old_max
        seal_mod._MODE_TRACKS_CACHE.clear()
