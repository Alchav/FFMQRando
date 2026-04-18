import pytest
import hashlib
from pathlib import Path

from archipelago_rooms_generator.rooms_generator import (
    LogicLink,
    MT19337Compat,
    SHUFFLING_DATA_PATH,
    _normalize_map_shuffle_mode,
    _read_yaml,
    _seed_to_uint32,
    _select_overworld_link,
    generate_rooms_yaml,
)

DATA_DIR = Path(__file__).resolve().parent


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


def test_select_overworld_link_prefers_switch_over_fixed_for_preferred_entrance():
    rng = MT19337Compat(1)
    switch_link = LogicLink(room=1, current={"entrance": 101}, origin={"entrance": 9, "teleporter": []})
    fixed_link = LogicLink(room=2, current={"entrance": 102}, origin={"entrance": 9, "teleporter": []})
    selected = _select_overworld_link(
        rng,
        [switch_link, fixed_link],
        room_location=None,
        preferred_entrance=9,
        seed_links_locations={101: None, 102: None},
        fixed_overworld_links=[fixed_link],
        switch_overworld_links=[switch_link],
        crystal_source_location=None,
    )
    assert selected is switch_link


def test_select_overworld_link_prefers_crystal_location_first():
    rng = MT19337Compat(1)
    switch_wrong = LogicLink(room=1, current={"entrance": 201}, origin={"entrance": 7, "teleporter": []})
    fixed_crystal = LogicLink(room=2, current={"entrance": 202}, origin={"entrance": 8, "teleporter": []})
    selected = _select_overworld_link(
        rng,
        [switch_wrong, fixed_crystal],
        room_location="BoneDungeon",
        preferred_entrance=7,
        seed_links_locations={201: "Windia", 202: "BoneDungeon"},
        fixed_overworld_links=[fixed_crystal],
        switch_overworld_links=[switch_wrong],
        crystal_source_location="BoneDungeon",
    )
    assert selected is fixed_crystal


def test_cross_impl_seed_matrix_hashes_match():
    fixture = _read_yaml(DATA_DIR / "cross_impl_seed_matrix.json")
    for case in fixture["cases"]:
        generated = generate_rooms_yaml(
            seed=case["seed"],
            map_shuffle=case["map_shuffle"],
            crest_shuffle=True,
            battlefield_shuffle=False,
            companion_shuffle=False,
            kaeli_mom=False,
        )
        digest = hashlib.sha256(generated.encode()).hexdigest()
        assert digest == case["sha256"], f"Mismatch for seed={case['seed']} map_shuffle={case['map_shuffle']}"


def test_overworld_shuffle_argument_changes_topology():
    base_kwargs = dict(
        seed="00000001",
        map_shuffle=2,
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
    )
    no_overworld = generate_rooms_yaml(**base_kwargs, overworld_shuffle=False)
    with_overworld = generate_rooms_yaml(**base_kwargs, overworld_shuffle=True)
    assert no_overworld != with_overworld
