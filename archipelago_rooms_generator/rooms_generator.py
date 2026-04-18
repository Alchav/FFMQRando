from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import random
from typing import Any

import json


DATA_DIR = Path(__file__).resolve().parent
ROOMS_PATH = DATA_DIR / "rooms.json"
ENTRANCE_PAIRS_PATH = DATA_DIR / "entrancespairs.json"
SHUFFLING_DATA_PATH = DATA_DIR / "shufflingdata.json"

CRESTS_ACCESS = {"LibraCrest", "GeminiCrest", "MobiusCrest"}
ITEM_ACCESS_REQ = {
    "LibraCrest": ["LibraCrest"],
    "GeminiCrest": ["GeminiCrest"],
    "MobiusCrest": ["MobiusCrest"],
}

MAP_SHUFFLE_DUNGEON_MODES = {"DungeonsInternal", "DungeonsMixed", "Everything", 1, 2, 3}


class MT19337Compat:
    """Best-effort MT19337 compatibility using Python's MT19937 core."""

    def __init__(self, seed: int):
        self._rng = random.Random(seed & 0xFFFFFFFF)

    def between(self, low: int, high: int) -> int:
        return self._rng.randrange(low, high + 1)

    def pick_from(self, seq: list[Any]):
        if not seq:
            raise ValueError("Cannot pick from empty sequence")
        return seq[self.between(0, len(seq) - 1)]

    def take_from(self, seq: list[Any]):
        val = self.pick_from(seq)
        seq.remove(val)
        return val

    def shuffle(self, seq: list[Any]) -> None:
        # Fisher-Yates, emulating common rando utility shuffles.
        for i in range(len(seq) - 1, 0, -1):
            j = self.between(0, i)
            seq[i], seq[j] = seq[j], seq[i]


@dataclass
class LogicLink:
    room: int
    current: dict[str, Any]
    origin: dict[str, Any]
    entrance_only: bool = False
    force_dead_end: bool = False
    force_link_destination: bool = False
    force_link_origin: bool = False
    forced_destination: int = 0
    forbidden_destinations: list[int] = field(default_factory=list)


@dataclass
class ClusterRoom:
    rooms: list[int]
    links: list[LogicLink] = field(default_factory=list)
    size: int = 0
    location: str | None = None

    def merge(self, room: "ClusterRoom") -> None:
        self.rooms += room.rooms
        self.links += room.links
        self.size += 1
        if self.location is None:
            self.location = room.location

    def update_links(self, origin_link: LogicLink, rng: MT19337Compat) -> None:
        if origin_link.force_link_origin:
            valid_origins = [x for x in self.links if not x.force_link_origin and not x.force_link_destination]
            if not valid_origins:
                raise RuntimeError("Floor Shuffle: One way Orientation Error")
            new_origin = rng.pick_from(valid_origins)
            new_origin.force_link_origin = True
            new_origin.forced_destination = origin_link.forced_destination

        if origin_link.force_dead_end:
            valid_dead_ends = [x for x in self.links if not x.force_link_origin and not x.force_link_destination]
            for link in valid_dead_ends:
                link.force_dead_end = True

        for link in self.links:
            link.forbidden_destinations.extend(origin_link.forbidden_destinations)


def _seed_to_uint32(seed: int | str) -> int:
    seed_str = str(seed).strip()
    seed_hex = seed_str.rjust(8, "0")[:8]
    # Match latest C# GenerateRooms() behavior: parse 8-char hex seed into 4 bytes before hashing.
    seed_bytes = bytes.fromhex(seed_hex)
    digest = hashlib.sha256(seed_bytes).digest()
    words = [int.from_bytes(digest[i : i + 4], "little") for i in range(0, 32, 4)]
    return sum(words) & 0xFFFFFFFF


def _normalize_map_shuffle_mode(map_shuffle: str | int) -> int | str:
    if isinstance(map_shuffle, int):
        return map_shuffle

    normalized = map_shuffle.strip().lower()
    aliases = {
        "none": 0,
        "dungeonsinternal": 1,
        "dungeonsmixed": 2,
        "everything": 3,
    }
    return aliases.get(normalized, map_shuffle)


def _read_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _room_by_id(rooms: list[dict[str, Any]], room_id: int) -> dict[str, Any]:
    for room in rooms:
        if room["id"] == room_id:
            return room
    raise KeyError(f"Room not found: {room_id}")


def _connect_link(rooms: list[dict[str, Any]], pending_links: list[tuple[int, dict[str, Any]]], link1: LogicLink, link2: LogicLink) -> None:
    room1_links = _room_by_id(rooms, link1.room)["links"]
    room2_links = _room_by_id(rooms, link2.room)["links"]
    if link1.current not in room1_links or link2.current not in room2_links:
        return
    room1_links.remove(link1.current)
    room2_links.remove(link2.current)

    pending_links.append(
        (
            link1.room,
            {
                "target_room": link2.room,
                "entrance": link1.current["entrance"],
                "teleporter": deepcopy(link2.origin["teleporter"]),
                "access": deepcopy(link1.current.get("access", [])),
            },
        )
    )
    pending_links.append(
        (
            link2.room,
            {
                "target_room": link1.room,
                "entrance": link2.current["entrance"],
                "teleporter": deepcopy(link1.origin["teleporter"]),
                "access": deepcopy(link2.current.get("access", [])),
            },
        )
    )


def _connect_overworld_link(
    rooms: list[dict[str, Any]],
    pending_links: list[tuple[int, dict[str, Any]]],
    location: str | None,
    link1: LogicLink,
    link2: LogicLink,
) -> None:
    room1_links = _room_by_id(rooms, link1.room)["links"]
    room2_links = _room_by_id(rooms, link2.room)["links"]
    if link1.current not in room1_links or link2.current not in room2_links:
        return
    room1_links.remove(link1.current)
    room2_links.remove(link2.current)

    link1_payload = {
        "target_room": link2.room,
        "entrance": link1.current["entrance"],
        "teleporter": deepcopy(link2.origin["teleporter"]),
        "access": deepcopy(link1.current.get("access", [])),
    }
    if location not in (None, "None"):
        link1_payload["location"] = location

    pending_links.append((link1.room, link1_payload))
    pending_links.append(
        (
            link2.room,
            {
                "target_room": link1.room,
                "entrance": link2.current["entrance"],
                "teleporter": deepcopy(link1.origin["teleporter"]),
                "access": deepcopy(link2.current.get("access", [])),
            },
        )
    )


def _select_overworld_link(
    rng: MT19337Compat,
    links_from_overworld: list[LogicLink],
    *,
    room_location: str | None,
    preferred_entrance: int | None,
    seed_links_locations: dict[int, str | None],
    fixed_overworld_links: list[LogicLink],
    switch_overworld_links: list[LogicLink],
    crystal_source_location: str | None,
) -> LogicLink:
    available = links_from_overworld.copy()
    if not available:
        raise ValueError("No overworld links available")

    available_ids = {id(l) for l in available}
    fixed_pool = [l for l in fixed_overworld_links if id(l) in available_ids]
    switch_pool = [l for l in switch_overworld_links if id(l) in available_ids]

    def by_location(pool: list[LogicLink], location: str | None) -> list[LogicLink]:
        if location in (None, "None"):
            return []
        return [l for l in pool if seed_links_locations.get(l.current.get("entrance")) == location]

    def by_preferred(pool: list[LogicLink]) -> list[LogicLink]:
        if preferred_entrance is None:
            return []
        return [l for l in pool if l.origin.get("entrance") == preferred_entrance]

    candidate_groups: list[list[LogicLink]] = []
    if crystal_source_location not in (None, "None"):
        candidate_groups.extend(
            [
                by_location(switch_pool, crystal_source_location),
                by_location(fixed_pool, crystal_source_location),
            ]
        )

    candidate_groups.extend(
        [
            by_preferred(switch_pool),
            by_preferred(fixed_pool),
            by_location(switch_pool, room_location),
            by_location(fixed_pool, room_location),
            switch_pool,
            fixed_pool,
            available,
        ]
    )

    for group in candidate_groups:
        if group:
            return rng.pick_from(group)
    return rng.pick_from(available)


def _crest_shuffle(rooms: list[dict[str, Any]], crest_shuffle: bool, rng: MT19337Compat) -> None:
    crest_list = [
        {"entrance": [67, 8], "origins": [64, 8], "deadend": True, "priority": 0},
        {"entrance": [68, 8], "origins": [65, 8], "deadend": True, "priority": 0},
        {"entrance": [69, 8], "origins": [66, 8], "deadend": True, "priority": 0},
        {"entrance": [72, 8], "origins": [45, 8], "deadend": False, "priority": 1},
        {"entrance": [59, 8], "origins": [60, 8], "deadend": False, "priority": 0},
        {"entrance": [60, 8], "origins": [59, 8], "deadend": True, "priority": 0},
        {"entrance": [64, 8], "origins": [67, 8], "deadend": False, "priority": 0},
        {"entrance": [65, 8], "origins": [68, 8], "deadend": False, "priority": 0},
        {"entrance": [66, 8], "origins": [69, 8], "deadend": False, "priority": 0},
        {"entrance": [62, 8], "origins": [63, 8], "deadend": True, "priority": 0},
        {"entrance": [63, 8], "origins": [62, 8], "deadend": False, "priority": 0},
        {"entrance": [45, 8], "origins": [72, 8], "deadend": False, "priority": 1},
        {"entrance": [54, 8], "origins": [44, 8], "deadend": False, "priority": 2},
        {"entrance": [71, 8], "origins": [70, 8], "deadend": False, "priority": 0},
        {"entrance": [70, 8], "origins": [71, 8], "deadend": True, "priority": 0},
        {"entrance": [44, 8], "origins": [54, 8], "deadend": False, "priority": 0},
        {"entrance": [43, 8], "origins": [61, 8], "deadend": False, "priority": 2},
        {"entrance": [61, 8], "origins": [43, 8], "deadend": True, "priority": 0},
    ]

    if not crest_shuffle:
        return

    crest_tiles = [
        "LibraCrest",
        "LibraCrest",
        "GeminiCrest",
        "GeminiCrest",
        "GeminiCrest",
        "MobiusCrest",
        "MobiusCrest",
        "MobiusCrest",
        "MobiusCrest",
    ]

    rng.shuffle(crest_list)
    crest_list.sort(key=lambda x: x["priority"], reverse=True)
    crest_priority: list[tuple[int, str]] = []
    new_link_to_process: list[tuple[int, dict[str, Any]]] = []

    while crest_list:
        deadend_count = sum(1 for x in crest_list if x["deadend"])
        passable_count = sum(1 for x in crest_list if not x["deadend"])

        crest1 = crest_list.pop(0)

        if crest1["deadend"]:
            non_deadend = [x for x in crest_list if not x["deadend"]]
            crest2 = rng.pick_from(non_deadend)
            crest_list.remove(crest2)
        else:
            if deadend_count < passable_count:
                crest2 = rng.take_from(crest_list)
            else:
                crest2 = [x for x in crest_list if x["deadend"]][0]
                crest_list.remove(crest2)

        if crest1["priority"] > 0:
            existing = [x for x in crest_priority if x[0] == crest1["priority"]]
            if existing:
                crest1_crest = existing[0][1]
                crest_tiles.remove(crest1_crest)
            else:
                crest1_crest = rng.take_from(crest_tiles)
                crest_priority.append((crest1["priority"], crest1_crest))
        else:
            crest1_crest = rng.take_from(crest_tiles)

        crest2_crest = crest1_crest
        if crest2["priority"] > 0 and not any(x[0] == crest2["priority"] for x in crest_priority):
            crest_priority.append((crest2["priority"], crest1_crest))

        crest1room = next(r for r in rooms if any(l.get("teleporter") == crest1["entrance"] for l in r["links"]))
        crest1link = next(l for l in crest1room["links"] if l.get("teleporter") == crest1["entrance"])
        crest2room = next(r for r in rooms if any(l.get("teleporter") == crest2["entrance"] for l in r["links"]))
        crest2link = next(l for l in crest2room["links"] if l.get("teleporter") == crest2["entrance"])

        crest1room["links"].remove(crest1link)
        crest2room["links"].remove(crest2link)

        access1 = [a for a in crest1link.get("access", []) if a not in CRESTS_ACCESS] + ITEM_ACCESS_REQ[crest1_crest]
        access2 = [a for a in crest2link.get("access", []) if a not in CRESTS_ACCESS] + ITEM_ACCESS_REQ[crest2_crest]

        new_link_to_process.append((crest1room["id"], {"target_room": crest2room["id"], "entrance": crest1link["entrance"], "teleporter": crest2["origins"], "access": access1}))
        new_link_to_process.append((crest2room["id"], {"target_room": crest1room["id"], "entrance": crest2link["entrance"], "teleporter": crest1["origins"], "access": access2}))

    for room_id, link in new_link_to_process:
        _room_by_id(rooms, room_id)["links"].append(link)


def _floor_shuffle(rooms: list[dict[str, Any]], map_shuffle: str | int, rng: MT19337Compat) -> None:
    map_shuffle = _normalize_map_shuffle_mode(map_shuffle)
    if map_shuffle not in MAP_SHUFFLE_DUNGEON_MODES:
        return

    include_temples_towns = map_shuffle in {"Everything", 3}
    intradungeon = map_shuffle in {"DungeonsInternal", 1}
    pending_links: list[tuple[int, dict[str, Any]]] = []

    entrances_pairs = _read_yaml(ENTRANCE_PAIRS_PATH)
    shuffling_data = _read_yaml(SHUFFLING_DATA_PATH)

    for room_id, target_room in shuffling_data.get("blocked_oneways", []):
        room = _room_by_id(rooms, room_id)
        room["links"] = [l for l in room["links"] if l.get("target_room") != target_room]

    for room_id, target_room, access_req in shuffling_data.get("added_links", []):
        _room_by_id(rooms, room_id)["links"].append({"target_room": target_room, "access": [int(access_req)]})

    room_links: list[tuple[int, dict[str, Any]]] = []
    for room in rooms:
        for link in room["links"]:
            if link.get("entrance", -1) >= 0:
                room_links.append((room["id"], link))

    def _find_entrance(eid: int):
        for rid, link in room_links:
            if link["entrance"] == eid:
                return rid, link
        raise KeyError(f"Entrance not found: {eid}")

    logic_links: list[LogicLink] = []
    for e0, e1 in entrances_pairs:
        r0, l0 = _find_entrance(e0)
        _, l1 = _find_entrance(e1)
        logic_links.append(LogicLink(r0, l0, l1))
    for e0, e1 in entrances_pairs:
        r1, l1 = _find_entrance(e1)
        _, l0 = _find_entrance(e0)
        logic_links.append(LogicLink(r1, l1, l0))

    room_triggers = []
    rooms_req = []
    for room in rooms:
        for obj in room.get("game_objects", []):
            if obj.get("type") == "Trigger":
                room_triggers.append((room["id"], obj.get("on_trigger", [])))
        for link in room["links"]:
            if link.get("access"):
                rooms_req.append((room["id"], link))

    forbidden_destinations = []
    for trigger_room_id, on_trigger in room_triggers:
        for room_id, link in rooms_req:
            if room_id != trigger_room_id and link.get("entrance", -1) != -1 and set(link.get("access", [])).intersection(on_trigger):
                forbidden_destinations.append((link["entrance"], trigger_room_id))

    if not include_temples_towns:
        towns_temples = set(shuffling_data["towns_temples"])
        logic_links = [x for x in logic_links if x.current["entrance"] not in towns_temples]

    forced_links = [(int(link[0]), int(link[1])) for link in shuffling_data.get("forced_links", [])]
    entrance_only = set(shuffling_data.get("entrance_only", []))
    forced_deadends = set(shuffling_data.get("forced_deadends", []))
    no_exits = set(shuffling_data.get("no_exits", []))
    priority_exits = set(shuffling_data.get("priority_exits", []))

    for link in logic_links:
        link.entrance_only = link.current["entrance"] in entrance_only
        link.force_dead_end = link.current["entrance"] in forced_deadends or link.current["entrance"] in no_exits

    for entrance, room in forbidden_destinations:
        target = next((l for l in logic_links if l.current["entrance"] == entrance), None)
        if target is not None:
            target.forbidden_destinations = [room]

    cluster_rooms: list[ClusterRoom] = []
    max_id = 0
    for room in rooms:
        internal_links = [x["target_room"] for x in room["links"] if x.get("entrance", -1) < 0] + [room["id"]]
        max_id = max(max_id, *internal_links)
        cluster_rooms.append(ClusterRoom(rooms=internal_links, links=[l for l in logic_links if l.room == room["id"]]))

    for i in range(max_id + 1):
        common = [x for x in cluster_rooms if i in x.rooms]
        if len(common) > 1:
            for room in common[1:]:
                cluster_rooms.remove(room)
                common[0].merge(room)

    # Crawl subregion links and stamp logical location on reachable clusters.
    room_to_cluster: dict[int, ClusterRoom] = {}
    for cluster in cluster_rooms:
        for room_id in cluster.rooms:
            room_to_cluster[room_id] = cluster

    location_links = []
    for room in rooms:
        if room.get("type") == "Subregion":
            for link in room.get("links", []):
                location = link.get("location")
                if location and location not in {"None", "GiantTree", "MacsShipDoom"}:
                    location_links.append((link.get("target_room"), location))

    for target_room, location in location_links:
        cluster = room_to_cluster.get(target_room)
        if cluster is not None and cluster.location is None:
            cluster.location = location

    # Forced links are direct entrance-to-entrance ties in latest C# shuffling data.
    for origin_entrance, destination_entrance in forced_links:
        origin_link = next((l for l in logic_links if l.current["entrance"] == origin_entrance), None)
        target_link = next((l for l in logic_links if l.current["entrance"] == destination_entrance), None)
        if origin_link is None or target_link is None:
            continue

        origin_cluster = next((c for c in cluster_rooms if origin_link in c.links), None)
        target_cluster = next((c for c in cluster_rooms if target_link in c.links), None)

        _connect_link(rooms, pending_links, origin_link, target_link)
        logic_links = [l for l in logic_links if l.current["entrance"] not in {origin_entrance, destination_entrance}]
        if origin_cluster is not None and origin_link in origin_cluster.links:
            origin_cluster.links.remove(origin_link)
        if target_cluster is not None and target_link in target_cluster.links:
            target_cluster.links.remove(target_link)

        if origin_cluster is not None and target_cluster is not None and origin_cluster is not target_cluster:
            origin_cluster.merge(target_cluster)
            cluster_rooms.remove(target_cluster)

    crest_rooms = [r["id"] for r in rooms if any(set(l.get("access", [])).intersection(CRESTS_ACCESS) for l in r["links"])]
    mac_ship_barred = set(crest_rooms + shuffling_data["mac_ship_exclusions"] + [x[1] for x in forbidden_destinations])
    mac_ship_deck = 187
    mac_ship_max_size = 4
    crystal_rooms = [
        {"location": "BoneDungeon", "target": 38, "base": 25},
        {"location": "IcePyramid", "target": 70, "base": 54},
        {"location": "LavaDome", "target": 121, "base": 100},
        {"location": "PazuzusTower", "target": 179, "base": 166},
    ]
    subregion_room_ids = {r["id"] for r in rooms if r.get("type") == "Subregion"}
    seed_links_locations = {
        int(link["entrance"]): link.get("location")
        for room in rooms
        if room.get("type") == "Subregion"
        for link in room.get("links", [])
        if link.get("entrance", -1) >= 0 and link.get("location") not in {None, "None"}
    }

    seed_rooms = [l["target_room"] for l in _room_by_id(rooms, 0)["links"] if l["target_room"] != 125]
    seed_cluster_rooms = [x for x in cluster_rooms if set(x.rooms).intersection(seed_rooms)]
    seed_shuffle = [x for x in seed_cluster_rooms if any(l.current["target_room"] == 0 for l in x.links)]
    seed_overworld_entrance = {
        id(cluster): next((l.current["entrance"] for l in cluster.links if l.current["target_room"] == 0), None)
        for cluster in seed_shuffle
    }
    seed_fixed = [x for x in seed_cluster_rooms if x not in seed_shuffle]
    seed_prog = [x for x in seed_shuffle if len(x.links) > 1]
    seed_dead = [x for x in seed_shuffle if len(x.links) == 1]

    init_prog = [x for x in cluster_rooms if len(x.links) > 1 and not set(x.rooms).intersection(seed_rooms) and 0 not in x.rooms] + seed_prog
    init_dead = [x for x in cluster_rooms if len(x.links) == 1 and not set(x.rooms).intersection(seed_rooms) and 0 not in x.rooms] + seed_dead

    rng.shuffle(init_prog)
    rng.shuffle(init_dead)

    if intradungeon:
        core_cluster_rooms = init_prog[: len(seed_prog)] + init_dead[: len(seed_dead)]
    else:
        non_crystal_prog = [x for x in init_prog if not set(x.rooms).intersection([c["target"] for c in crystal_rooms])]
        non_crystal_dead = [x for x in init_dead if not set(x.rooms).intersection([c["target"] for c in crystal_rooms])]
        core_cluster_rooms = non_crystal_prog[: len(seed_prog)] + non_crystal_dead[: len(seed_dead)]
    if intradungeon:
        seed_locations = [x.location for x in seed_prog + seed_dead]
        loc_progress = [x for x in init_prog if x.location is not None]
        loc_dead = [x for x in init_dead if x.location is not None]
        selected: list[ClusterRoom] = []
        for loc in seed_locations:
            pool = [x for x in (loc_progress + loc_dead) if x.location == loc and x not in selected]
            if pool:
                selected.append(rng.pick_from(pool))
        if len(selected) == len(seed_locations):
            core_cluster_rooms = selected
    valid_seed_switch = [x for x in seed_shuffle if x not in core_cluster_rooms]
    fixed_overworld_links = [
        link
        for cluster in seed_fixed
        if set(cluster.rooms).intersection(subregion_room_ids)
        for link in cluster.links
    ]
    switch_overworld_links = [
        link
        for cluster in valid_seed_switch
        if set(cluster.rooms).intersection(subregion_room_ids)
        for link in cluster.links
    ]

    for room in core_cluster_rooms:
        valid_links = [x for x in room.links if not x.force_dead_end and not x.entrance_only]
        if not valid_links:
            continue
        priority_links = [x for x in valid_links if x.current["entrance"] in priority_exits]
        if priority_links:
            valid_links = priority_links
        core_link = rng.pick_from(valid_links)
        room.links.remove(core_link)

        links_from_overworld = [
            link
            for cluster in cluster_rooms
            if set(cluster.rooms).intersection(subregion_room_ids)
            for link in cluster.links
        ]
        if not links_from_overworld:
            continue

        preferred_entrance = seed_overworld_entrance.get(id(room))
        crystal_source_location = next(
            (c["location"] for c in crystal_rooms if set(room.rooms).intersection({c["target"], c["base"]})),
            None,
        )
        ow_link = _select_overworld_link(
            rng,
            links_from_overworld,
            room_location=room.location,
            preferred_entrance=preferred_entrance,
            seed_links_locations=seed_links_locations,
            fixed_overworld_links=fixed_overworld_links,
            switch_overworld_links=switch_overworld_links,
            crystal_source_location=crystal_source_location,
        )
        ow_cluster = next((cluster for cluster in cluster_rooms if ow_link in cluster.links), None)
        if ow_cluster is not None:
            ow_cluster.links.remove(ow_link)

        _connect_overworld_link(
            rooms,
            pending_links,
            seed_links_locations.get(ow_link.current.get("entrance")) or room.location,
            ow_link,
            core_link,
        )

    core_cluster_rooms = core_cluster_rooms + seed_fixed
    core_ids = set([0] + [rid for c in core_cluster_rooms for rid in c.rooms])
    progress_cluster_rooms = [x for x in cluster_rooms if len(x.links) > 1 and not set(x.rooms).intersection(core_ids)]
    deadend_cluster_rooms = [x for x in cluster_rooms if len(x.links) == 1 and not set(x.rooms).intersection(core_ids)]

    rng.shuffle(core_cluster_rooms)
    core_cluster_rooms = [x for x in core_cluster_rooms if x.links]

    if intradungeon:
        # Attempt C#-like per-location valid assembly loop for intradungeon mode.
        for origin_room in core_cluster_rooms:
            if not origin_room.links or origin_room.location is None:
                continue

            loc_progress = [x for x in progress_cluster_rooms if x.location == origin_room.location]
            loc_dead = [x for x in deadend_cluster_rooms if x.location == origin_room.location]
            if not loc_progress and not loc_dead:
                continue

            valid_pairs: list[tuple[LogicLink, LogicLink]] | None = None
            chosen_progress: list[ClusterRoom] = []
            chosen_dead: list[ClusterRoom] = []

            for _attempt in range(120):
                working_links = origin_room.links.copy()
                pairs: list[tuple[LogicLink, LogicLink]] = []
                valid = True

                chosen_progress = loc_progress.copy()
                chosen_dead = loc_dead.copy()
                rng.shuffle(chosen_progress)
                rng.shuffle(chosen_dead)

                # Progress placement
                for dest in chosen_progress:
                    origin_candidates = [l for l in working_links if not l.force_link_destination]
                    if not origin_candidates:
                        valid = False
                        break
                    origin_link = rng.pick_from(origin_candidates)

                    if set(dest.rooms).intersection(origin_link.forbidden_destinations):
                        valid = False
                        break

                    dest_candidates = [l for l in dest.links if not l.entrance_only and not l.force_dead_end and not l.force_link_origin and not l.force_link_destination]
                    if not dest_candidates:
                        valid = False
                        break
                    priority_dest = [l for l in dest_candidates if l.current["entrance"] in priority_exits]
                    if priority_dest:
                        dest_candidates = priority_dest
                    dest_link = rng.pick_from(dest_candidates)

                    pairs.append((origin_link, dest_link))
                    working_links.remove(origin_link)

                    # Merge destination links into working pool with C#-like inherited restrictions.
                    for merged in [l for l in dest.links if l is not dest_link]:
                        merged.forbidden_destinations.extend(origin_link.forbidden_destinations)
                        if origin_link.force_dead_end and not merged.force_link_origin and not merged.force_link_destination:
                            merged.force_dead_end = True
                        working_links.append(merged)

                if not valid:
                    continue

                # Deadend placement
                for dest in chosen_dead:
                    origin_candidates = [l for l in working_links if l.force_dead_end]
                    if not origin_candidates:
                        origin_candidates = working_links
                    if not origin_candidates or not dest.links:
                        valid = False
                        break
                    origin_link = rng.pick_from(origin_candidates)
                    if set(dest.rooms).intersection(origin_link.forbidden_destinations):
                        valid = False
                        break
                    dest_link = rng.pick_from(dest.links)
                    pairs.append((origin_link, dest_link))
                    working_links.remove(origin_link)
                    working_links.extend([l for l in dest.links if l is not dest_link])

                if not valid:
                    continue

                # Validate leftovers (no forced deadends, even links), then pair leftovers.
                if any(l.force_dead_end for l in working_links) or (len(working_links) % 2 == 1):
                    continue

                while working_links:
                    first = rng.take_from(working_links)
                    second = rng.take_from(working_links)
                    pairs.append((first, second))

                valid_pairs = pairs
                break

            if valid_pairs is None:
                continue

            for link_a, link_b in valid_pairs:
                _connect_link(rooms, pending_links, link_a, link_b)

            for dest in chosen_progress:
                if dest in progress_cluster_rooms:
                    progress_cluster_rooms.remove(dest)
                    origin_room.merge(dest)
            for dest in chosen_dead:
                if dest in deadend_cluster_rooms:
                    deadend_cluster_rooms.remove(dest)
                    origin_room.merge(dest)

    guard = 0
    intradungeon_progress_retries = 0
    while progress_cluster_rooms:
        guard += 1
        if guard > 10000:
            if intradungeon and intradungeon_progress_retries < 3:
                intradungeon_progress_retries += 1
                guard = 0
                rng.shuffle(progress_cluster_rooms)
                continue
            deadend_cluster_rooms.extend(progress_cluster_rooms)
            progress_cluster_rooms = []
            break
        if intradungeon:
            same_loc_origins = [
                r for r in core_cluster_rooms
                if r.links and any(d.location is None or r.location is None or d.location == r.location for d in progress_cluster_rooms)
            ]
            origin_room = rng.pick_from(same_loc_origins if same_loc_origins else core_cluster_rooms)
        else:
            origin_room = rng.pick_from(core_cluster_rooms)
        origin_links = [x for x in origin_room.links if not x.force_link_destination]
        if not origin_links:
            continue
        origin_link = rng.pick_from(origin_links)

        dest_rooms = [
            x
            for x in progress_cluster_rooms
            if (not intradungeon) or (x.location is None or origin_room.location is None or x.location == origin_room.location)
            if not set(x.rooms).intersection(origin_link.forbidden_destinations)
            and ((not origin_link.force_dead_end) or ((not set(x.rooms).intersection(crest_rooms)) and (len(x.links) % 2 == 0)))
            and ((mac_ship_deck not in origin_room.rooms) or (not set(x.rooms).intersection(mac_ship_barred)))
        ]
        if not dest_rooms or (mac_ship_deck in origin_room.rooms and origin_room.size >= mac_ship_max_size):
            continue

        dest = rng.pick_from(dest_rooms)
        progress_cluster_rooms.remove(dest)

        dest_links = [x for x in dest.links if not x.entrance_only and not x.force_dead_end]
        priority_dest_links = [x for x in dest_links if x.current["entrance"] in priority_exits]
        if priority_dest_links:
            dest_links = priority_dest_links
        if not dest_links:
            progress_cluster_rooms.append(dest)
            continue
        dest_link = rng.pick_from(dest_links)

        origin_room.links.remove(origin_link)
        dest.links.remove(dest_link)
        _connect_link(rooms, pending_links, origin_link, dest_link)
        dest.update_links(origin_link, rng)
        origin_room.merge(dest)

    sky_target = None
    if not intradungeon:
        # Place sky crystal room (Pazuzu) similar to C# handling as a dedicated progress placement.
        sky_room = next(c for c in crystal_rooms if c["location"] == "PazuzusTower")
        sky_target, sky_base = sky_room["target"], sky_room["base"]
        sky_cluster = next((x for x in progress_cluster_rooms if sky_target in x.rooms), None)
        if sky_cluster is not None:
            progress_cluster_rooms.remove(sky_cluster)
            sky_origin = next(
                (o for o in core_cluster_rooms if (o.location == sky_room["location"] or sky_base in o.rooms) and o.links),
                None,
            )
            if sky_origin is not None and sky_cluster.links:
                origin_link = rng.pick_from(sky_origin.links)
                sky_origin.links.remove(origin_link)
                dest_link = rng.take_from(sky_cluster.links)
                _connect_link(rooms, pending_links, origin_link, dest_link)
                sky_origin.merge(sky_cluster)

    # Place crystal deadends at their respective base locations before generic deadend placement.
    for crystal in crystal_rooms:
        if crystal["target"] == sky_target:
            continue
        crystal_cluster = next((x for x in deadend_cluster_rooms if crystal["target"] in x.rooms), None)
        if crystal_cluster is None:
            continue
        deadend_cluster_rooms.remove(crystal_cluster)
        crystal_origin = next(
            (o for o in core_cluster_rooms if (o.location == crystal["location"] or crystal["base"] in o.rooms) and o.links),
            None,
        )
        if crystal_origin is None or not crystal_cluster.links:
            deadend_cluster_rooms.append(crystal_cluster)
            continue
        origin_link = rng.pick_from(crystal_origin.links)
        crystal_origin.links.remove(origin_link)
        dest_link = rng.take_from(crystal_cluster.links)
        _connect_link(rooms, pending_links, origin_link, dest_link)
        crystal_origin.merge(crystal_cluster)

    for room in core_cluster_rooms:
        dead_links = [x for x in room.links if x.force_dead_end]
        while dead_links:
            origin_link = dead_links.pop(0)
            dest_rooms = [x for x in deadend_cluster_rooms if not set(x.rooms).intersection(crest_rooms) and not set(x.rooms).intersection(origin_link.forbidden_destinations) and ((mac_ship_deck not in room.rooms) or not set(x.rooms).intersection(mac_ship_barred))]
            if intradungeon:
                dest_rooms = [x for x in dest_rooms if x.location is None or room.location is None or x.location == room.location]
            if not dest_rooms:
                continue
            room.links.remove(origin_link)
            dest = rng.pick_from(dest_rooms)
            dest_link = rng.take_from(dest.links)
            deadend_cluster_rooms.remove(dest)
            _connect_link(rooms, pending_links, origin_link, dest_link)
            room.merge(dest)

        if len(room.links) % 2 == 1:
            origin_link = rng.pick_from(room.links)
            dest_rooms = [x for x in deadend_cluster_rooms if not set(x.rooms).intersection(origin_link.forbidden_destinations) and ((mac_ship_deck not in room.rooms) or not set(x.rooms).intersection(mac_ship_barred))]
            if intradungeon:
                dest_rooms = [x for x in dest_rooms if x.location is None or room.location is None or x.location == room.location]
            if not dest_rooms:
                continue
            dest = rng.pick_from(dest_rooms)
            dest_link = rng.take_from(dest.links)
            deadend_cluster_rooms.remove(dest)
            room.links.remove(origin_link)
            _connect_link(rooms, pending_links, origin_link, dest_link)
            room.merge(dest)

    if len(deadend_cluster_rooms) % 2 == 1:
        origin_link = {"target_room": 500, "entrance": 0, "teleporter": [141, 1], "access": []}
        destination_link = {"target_room": 0, "entrance": 481, "teleporter": [0, 10], "access": []}
        deadend_cluster_rooms.append(ClusterRoom(rooms=[500], links=[LogicLink(500, destination_link, origin_link)]))
        rooms.append({"name": "Dummy Room", "id": 500, "game_objects": [], "links": []})

    mac_exception_count = 0
    intradungeon_deadend_retries = 0
    while deadend_cluster_rooms:
        rng.shuffle(deadend_cluster_rooms)
        destination_rooms = [deadend_cluster_rooms[0], deadend_cluster_rooms[1]]

        origin_candidates = [
            x
            for x in core_cluster_rooms
            if x.links
        ]
        no_exit_candidates = [x for x in origin_candidates if any(l.force_dead_end for l in x.links)]
        odd_candidates = [x for x in origin_candidates if len(x.links) % 2 == 1]
        unfilled = [
            x
            for x in (no_exit_candidates or odd_candidates or origin_candidates)
            if not set([d for l in x.links for d in l.forbidden_destinations]).intersection([rid for d in destination_rooms for rid in d.rooms])
            and ((not mac_ship_barred.intersection([rid for d in destination_rooms for rid in d.rooms])) or (mac_ship_deck not in x.rooms))
        ]
        if not unfilled:
            mac_exception_count += 1
            if mac_exception_count > 50:
                if intradungeon and intradungeon_deadend_retries < 3:
                    intradungeon_deadend_retries += 1
                    mac_exception_count = 0
                    rng.shuffle(deadend_cluster_rooms)
                    continue
                break
            continue

        origin_room = rng.pick_from(unfilled)
        deadend_cluster_rooms.remove(destination_rooms[0])
        deadend_cluster_rooms.remove(destination_rooms[1])

        for dest in destination_rooms:
            origin_link_pool = [l for l in origin_room.links if l.force_dead_end]
            if not origin_link_pool:
                origin_link_pool = origin_room.links
            origin_link = rng.pick_from(origin_link_pool)
            origin_room.links.remove(origin_link)
            dest_link = rng.take_from(dest.links)
            _connect_link(rooms, pending_links, origin_link, dest_link)
            origin_room.merge(dest)

    for room in core_cluster_rooms:
        while room.links:
            if len(room.links) % 2 == 1:
                break
            _connect_link(rooms, pending_links, rng.take_from(room.links), rng.take_from(room.links))

    for room_id, link in pending_links:
        _room_by_id(rooms, room_id)["links"].append(link)


def _yaml_quote(s: str) -> str:
    if s == "" or any(ch in s for ch in [":", "#", "[", "]", "{", "}", "\n", "\"", "'"]) or s.strip() != s:
        return json.dumps(s)
    return s


def _to_yaml(obj: Any, indent: int = 0) -> str:
    sp = " " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            key = _yaml_quote(str(k))
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{key}:")
                lines.append(_to_yaml(v, indent + 2))
            else:
                lines.append(f"{sp}{key}: {_to_yaml(v, 0).strip()}")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return f"{sp}[]"
        lines = []
        for item in obj:
            if isinstance(item, (dict, list)):
                rendered = _to_yaml(item, indent + 2)
                first, *rest = rendered.splitlines()
                lines.append(f"{sp}- {first.strip()}")
                lines.extend(rest)
            else:
                lines.append(f"{sp}- {_to_yaml(item, 0).strip()}")
        return "\n".join(lines)
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if obj is None:
        return "null"
    if isinstance(obj, str):
        return _yaml_quote(obj)
    return str(obj)


def generate_rooms_yaml(
    seed: int | str,
    map_shuffle: str | int,
    crest_shuffle: bool,
    battlefield_shuffle: bool,
    companion_shuffle: bool,
    kaeli_mom: bool,
) -> str:
    """
    Generate a shuffled rooms.yaml payload without calling the FFMQR Web API.

    Parameters are API-compatible; battlefield_shuffle / companion_shuffle / kaeli_mom are
    accepted for Archipelago compatibility but do not modify room-link topology in this module.
    """
    _ = (battlefield_shuffle, companion_shuffle, kaeli_mom)

    rooms = _read_yaml(ROOMS_PATH)
    rng = MT19337Compat(_seed_to_uint32(seed))

    _crest_shuffle(rooms, crest_shuffle=crest_shuffle, rng=rng)
    _floor_shuffle(rooms, map_shuffle=map_shuffle, rng=rng)

    return _to_yaml(rooms)


if __name__ == "__main__":
    out = generate_rooms_yaml(
        seed="00000001",
        map_shuffle="DungeonsMixed",
        crest_shuffle=True,
        battlefield_shuffle=False,
        companion_shuffle=False,
        kaeli_mom=False,
    )
    print(out)
