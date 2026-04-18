import contextlib
import hashlib
import json
import os
import subprocess
from itertools import product
from pathlib import Path

import pytest
import yaml

from archipelago_rooms_generator.rooms_generator import (
    LogicLink,
    MT19337Compat,
    ROOMS_PATH,
    SHUFFLING_DATA_PATH,
    _normalize_map_shuffle_mode,
    _read_yaml,
    _seed_to_uint32,
    _generate_rooms_yaml_with_rng,
    _select_overworld_link,
    _shuffle_battlefield_rewards,
    _companions_shuffle,
    generate_rooms_yaml,
)

DATA_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATA_DIR.parent
TRACE_PARITY_ENABLED = os.environ.get("FFMQR_TRACE_PARITY") == "1"
TRACE_CASES = [
    dict(seed="00000001", map_shuffle=1, crest_shuffle=False, battlefield_shuffle=False, companion_shuffle=0, kaeli_mom=False, overworld_shuffle=False),
    dict(seed="00000001", map_shuffle=1, crest_shuffle=True, battlefield_shuffle=False, companion_shuffle=1, kaeli_mom=False, overworld_shuffle=False),
    dict(seed="0000000D", map_shuffle=2, crest_shuffle=True, battlefield_shuffle=False, companion_shuffle=0, kaeli_mom=False, overworld_shuffle=False),
    dict(seed="0000000D", map_shuffle=2, crest_shuffle=True, battlefield_shuffle=True, companion_shuffle=2, kaeli_mom=False, overworld_shuffle=True),
    dict(seed="00000022", map_shuffle=3, crest_shuffle=True, battlefield_shuffle=False, companion_shuffle=1, kaeli_mom=True, overworld_shuffle=True),
]
SMOKE_OPTION_MATRIX = list(product([0, 1, 2, 3], [False, True], [False, True], [0, 1, 2], [False, True], [False, True]))


def _stable_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReplayRng:
    def __init__(self, trace: list[dict]):
        self._trace = trace
        self._index = 0

    @staticmethod
    def _field(step: dict, name: str):
        return step.get(name, step.get(name[:1].upper() + name[1:]))

    def _next(self, kind: str, count: int) -> dict:
        assert self._index < len(self._trace), f"Replay exhausted before {kind} count={count}"
        step = self._trace[self._index]
        self._index += 1
        step_kind = self._field(step, "kind")
        step_count = self._field(step, "count")
        assert step_kind == kind, f"Expected {kind}, got {step_kind} at trace step {self._index - 1}"
        assert step_count == count, f"Expected count {count}, got {step_count} for {kind} at trace step {self._index - 1}"
        return step

    def between(self, low: int, high: int) -> int:
        raise AssertionError(f"ReplayRng should not receive raw between({low}, {high}) calls")

    def pick_from(self, seq: list):
        step = self._next("pick", len(seq))
        return seq[self._field(step, "index")]

    def take_from(self, seq: list):
        step = self._next("take", len(seq))
        value = seq[self._field(step, "index")]
        removed_index = seq.index(value)
        assert removed_index == self._field(step, "removedIndex")
        seq.remove(value)
        return value

    def shuffle(self, seq: list) -> None:
        step = self._next("shuffle", len(seq))
        swaps = self._field(step, "swaps")
        assert len(swaps) == max(len(seq) - 1, 0)
        for i, j in zip(range(len(seq) - 1, 0, -1), swaps):
            seq[i], seq[j] = seq[j], seq[i]

    def assert_exhausted(self) -> None:
        assert self._index == len(self._trace), f"Replay stopped at {self._index} of {len(self._trace)} steps"


def _dotnet_executable() -> str | None:
    preferred = Path("/home/alchav/.dotnet/dotnet")
    if preferred.exists():
        return str(preferred)
    fallback = subprocess.run(["bash", "-lc", "command -v dotnet"], capture_output=True, text=True, cwd=REPO_ROOT)
    if fallback.returncode == 0:
        return fallback.stdout.strip()
    return None


@contextlib.contextmanager
def _built_trace_runner():
    dotnet = _dotnet_executable()
    if dotnet is None:
        pytest.skip("dotnet is not available")

    env = os.environ.copy()
    env["DOTNET_CLI_HOME"] = "/tmp"
    env["HOME"] = "/tmp"
    env["NUGET_PACKAGES"] = "/home/alchav/.nuget/packages"

    build = subprocess.run(
        [dotnet, "build", "FFMQRTraceRunner/FFMQRTraceRunner.csproj", "-c", "Debug", "--configfile", "Temporary.NuGet.Config", "--nologo"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    if build.returncode != 0:
        pytest.skip(f"temporary trace runner build failed:\n{build.stdout}\n{build.stderr}")
    yield {"dotnet": dotnet, "env": env}


@pytest.fixture(scope="session")
def trace_runner():
    with _built_trace_runner() as runner:
        yield runner


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


@pytest.mark.parametrize(
    ("map_shuffle", "crest_shuffle", "battlefield_shuffle", "companion_shuffle", "kaeli_mom", "overworld_shuffle"),
    SMOKE_OPTION_MATRIX,
)
def test_generate_rooms_yaml_smoke(
    map_shuffle,
    crest_shuffle,
    battlefield_shuffle,
    companion_shuffle,
    kaeli_mom,
    overworld_shuffle,
):
    generated = generate_rooms_yaml(
        seed="00000001",
        map_shuffle=map_shuffle,
        crest_shuffle=crest_shuffle,
        battlefield_shuffle=battlefield_shuffle,
        companion_shuffle=companion_shuffle,
        kaeli_mom=kaeli_mom,
        overworld_shuffle=overworld_shuffle,
    )
    assert isinstance(generated, list)
    assert generated


def test_internal_and_mixed_modes_are_distinct():
    internal = generate_rooms_yaml(
        seed="00000001",
        map_shuffle=1,
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
        overworld_shuffle=False,
    )
    mixed = generate_rooms_yaml(
        seed="00000001",
        map_shuffle=2,
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
        overworld_shuffle=False,
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
            overworld_shuffle=False,
        )
        digest = _stable_digest(generated)
        assert digest == case["sha256"], f"Mismatch for seed={case['seed']} map_shuffle={case['map_shuffle']}"


def test_battlefield_logic_marks_gold_rewards_with_gp_trigger():
    rooms = _read_yaml(ROOMS_PATH)
    rng = MT19337Compat(1)
    _shuffle_battlefield_rewards(rooms, battlefield_shuffle=False, rng=rng)
    foresta_subregion = next(room for room in rooms if room["id"] == 220)
    gold_battlefield = next(obj for obj in foresta_subregion["game_objects"] if obj["object_id"] == 3)
    assert gold_battlefield["type"] == "BattlefieldGp"
    assert gold_battlefield["on_trigger"] == ["Gp150"]


def test_companion_shuffle_moves_companions_in_nonstandard_mode():
    rooms = _read_yaml(ROOMS_PATH)
    rng = MT19337Compat(1)
    _companions_shuffle(rooms, companion_shuffle=1, kaeli_mom=False, rng=rng)
    companion_rooms = {
        room["id"]: sorted(
            obj["name"]
            for obj in room.get("game_objects", [])
            if set(obj.get("on_trigger", [])).intersection({"Kaeli", "Tristam", "Phoebe", "Reuben", "TreeWitherPerson"})
        )
        for room in rooms
    }
    assert companion_rooms[17] != ["Kaeli Companion", "Tree Wither Person"]
    assert sum(1 for names in companion_rooms.values() if names) == 4


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


@pytest.mark.skipif(not TRACE_PARITY_ENABLED, reason="temporary C# trace parity harness is opt-in")
@pytest.mark.parametrize("case", TRACE_CASES)
def test_trace_replay_matches_csharp_logic(case, trace_runner):
    result = subprocess.run(
        [
            trace_runner["dotnet"],
            "FFMQRTraceRunner/bin/Debug/net7.0/FFMQRTraceRunner.dll",
            case["seed"],
            str(case["map_shuffle"]),
            str(case["crest_shuffle"]).lower(),
            str(case["battlefield_shuffle"]).lower(),
            str(case["companion_shuffle"]),
            str(case["kaeli_mom"]).lower(),
            str(case["overworld_shuffle"]).lower(),
        ],
        cwd=REPO_ROOT,
        env=trace_runner["env"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    json_line = next(line for line in reversed(result.stdout.splitlines()) if line.strip().startswith("{"))
    payload = json.loads(json_line)
    trace = payload.get("trace", payload.get("Trace"))
    yaml_text = payload.get("yaml", payload.get("Yaml"))

    replay_rng = ReplayRng(trace)
    generated = _generate_rooms_yaml_with_rng(
        rng=replay_rng,
        map_shuffle=case["map_shuffle"],
        crest_shuffle=case["crest_shuffle"],
        battlefield_shuffle=case["battlefield_shuffle"],
        companion_shuffle=case["companion_shuffle"],
        kaeli_mom=case["kaeli_mom"],
        overworld_shuffle=case["overworld_shuffle"],
    )
    replay_rng.assert_exhausted()
    assert generated == yaml.safe_load(yaml_text)
