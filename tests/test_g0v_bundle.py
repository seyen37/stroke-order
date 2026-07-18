"""W1-D（架構健檢 2026-07-18）：g0v bundle 快取層與 timeout 契約。"""
from __future__ import annotations

import gzip
import json

import pytest

from stroke_order.sources.g0v import G0VSource, CharacterNotFound

FAKE_STROKES = [
    {
        "outline": [{"type": "M", "x": 100.0, "y": 100.0}],
        "track": [{"x": 100.0, "y": 100.0}, {"x": 200.0, "y": 200.0}],
    }
]


def _make_source(tmp_path, with_bundle: bool, char: str = "永") -> G0VSource:
    bundle_path = tmp_path / "g0v_bundle.json.gz"
    if with_bundle:
        payload = {f"{ord(char):x}": FAKE_STROKES}
        with gzip.open(bundle_path, "wt", encoding="utf-8") as f:
            json.dump(payload, f)
    return G0VSource(
        cache_dir=tmp_path / "cache",
        allow_network=False,
        bundle_path=bundle_path,
    )


def test_bundle_hit_without_network(tmp_path):
    src = _make_source(tmp_path, with_bundle=True)
    ch = src.get_character("永")
    assert len(ch.strokes) == 1
    assert ch.strokes[0].track[1].x == 200.0


def test_missing_bundle_degrades_gracefully(tmp_path):
    src = _make_source(tmp_path, with_bundle=False)
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_file_cache_takes_precedence_over_bundle(tmp_path):
    """既有 per-char 快取檔（可能較新）優先於 bundle。"""
    src = _make_source(tmp_path, with_bundle=True)
    newer = [dict(FAKE_STROKES[0], track=[{"x": 1.0, "y": 1.0}])]
    cache_file = src.cache_dir / f"{ord('永'):x}.json"
    cache_file.write_text(json.dumps(newer), encoding="utf-8")
    ch = src.get_character("永")
    assert ch.strokes[0].track[0].x == 1.0


def test_corrupt_bundle_degrades_gracefully(tmp_path):
    bundle_path = tmp_path / "g0v_bundle.json.gz"
    bundle_path.write_bytes(b"not gzip at all")
    src = G0VSource(
        cache_dir=tmp_path / "cache", allow_network=False, bundle_path=bundle_path
    )
    with pytest.raises(CharacterNotFound):
        src.get_character("永")


def test_default_timeout_is_short(tmp_path):
    """W1-D：預設 timeout 10s → 3s（sync def 路由下界定最壞延遲）。"""
    src = G0VSource(cache_dir=tmp_path / "cache", allow_network=False)
    assert src.timeout == 3.0


def test_socket_timeout_maps_to_character_not_found(tmp_path, monkeypatch):
    """W1-D 回歸鎖：socket 讀取逾時（裸 TimeoutError）不可炸穿到呼叫端。"""
    import urllib.request

    def _boom(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    src = G0VSource(cache_dir=tmp_path / "cache", allow_network=True)
    with pytest.raises(CharacterNotFound):
        src.get_character("\U000203b5")  # 罕字，不會在 cache/bundle
