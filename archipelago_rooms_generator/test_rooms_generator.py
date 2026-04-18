import pytest

from archipelago_rooms_generator.rooms_generator import _normalize_map_shuffle_mode, _read_yaml, _seed_to_uint32, SHUFFLING_DATA_PATH, generate_rooms_yaml


def test_map_shuffle_aliases():
    assert _normalize_map_shuffle_mode("DungeonsMixed") == 2
    assert _normalize_map_shuffle_mode("DungeonsInternal") == 1
    assert _normalize_map_shuffle_mode(3) == 3


def test_seed_hex_and_fallback():
    assert _seed_to_uint32("1") == _seed_to_uint32("00000001")


def test_seed_requires_hex():
    with pytest.raises(ValueError):
        _seed_to_uint32("example-seed")


def test_shufflingdata_uses_current_schema():
    data = _read_yaml(SHUFFLING_DATA_PATH)
    assert "priority_exits" in data
    assert "no_exits" in data
    assert "blocked_oneways" in data


def test_internal_and_mixed_modes_are_distinct():
    internal = generate_rooms_yaml(
        seed="00000001",
        map_shuffle=1,
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
    )
    mixed = generate_rooms_yaml(
        seed="00000001",
        map_shuffle=2,
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
    )
    assert internal != mixed
