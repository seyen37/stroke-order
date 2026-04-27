"""Tests for 朱邦復 2018 radical classification."""
from stroke_order.radicals import RadicalCategory, all_radicals, lookup


def test_natural_body_radicals():
    assert lookup("日") == RadicalCategory("本存", "本體")
    assert lookup("月") == RadicalCategory("本存", "本體")
    assert lookup("水") == RadicalCategory("本存", "本體")


def test_plant_radicals():
    assert lookup("木") == RadicalCategory("本存", "植物")
    assert lookup("竹") == RadicalCategory("本存", "植物")


def test_body_parts():
    assert lookup("目") == RadicalCategory("本存", "肢體")
    assert lookup("手") == RadicalCategory("本存", "肢體")
    assert lookup("心") == RadicalCategory("本存", "肢體")


def test_animal():
    assert lookup("鳥") == RadicalCategory("本存", "動物")
    assert lookup("馬") == RadicalCategory("本存", "動物")


def test_manmade_food_clothing():
    assert lookup("皿") == RadicalCategory("人造", "食衣")
    assert lookup("糸") == RadicalCategory("人造", "食衣")


def test_manmade_transportation():
    assert lookup("車") == RadicalCategory("人造", "住行")
    assert lookup("舟") == RadicalCategory("人造", "住行")
    assert lookup("門") == RadicalCategory("人造", "住行")


def test_normative_fundamentals():
    assert lookup("力") == RadicalCategory("規範", "根源")
    assert lookup("火") == RadicalCategory("規範", "根源")


def test_applied_messaging():
    assert lookup("言") == RadicalCategory("應用", "訊息")


def test_applied_relations():
    assert lookup("生") == RadicalCategory("應用", "關係")
    assert lookup("子") == RadicalCategory("應用", "關係")


def test_unclassified_char_returns_none():
    # 永 isn't a radical
    assert lookup("永") is None
    # Private-use area
    assert lookup("\ue000") is None


def test_all_radicals_is_sorted_and_deduped():
    rads = all_radicals()
    assert len(rads) > 100  # around 136
    assert rads == sorted(rads)
    assert len(rads) == len(set(rads))
