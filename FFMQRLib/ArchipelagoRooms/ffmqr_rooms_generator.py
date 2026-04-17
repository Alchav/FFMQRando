"""Local replacement for the FFMQRWebAPI rooms.yaml endpoint.

This module exposes `generate_rooms_yaml(...)`, which can be imported from
Archipelago code to produce the shuffled rooms.yaml payload without using the
remote ffmqr API.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT = _THIS_DIR / "FFMQRRoomsGenerator.csproj"
_DLL = _THIS_DIR / "bin" / "Release" / "net8.0" / "FFMQRRoomsGenerator.dll"


def _to_bool_str(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return "true"
    if text in {"0", "false", "no", "off"}:
        return "false"
    raise ValueError(f"Invalid boolean value: {value!r}")


def _build_if_needed() -> None:
    if _DLL.exists():
        return

    cmd = ["dotnet", "build", str(_PROJECT), "-c", "Release"]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to build FFMQRRoomsGenerator.\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )


def generate_rooms_yaml(
    seed: str | int,
    map_shuffle: str | bool | int,
    crest_shuffle: bool | int | str,
    battlefield_shuffle: bool | int | str,
    companion_shuffle: bool | int | str,
    kaeli_mom: bool | int | str,
) -> str:
    """Return the generated rooms.yaml text for the given options.

    Args:
        seed: Seed value sent to the original API.
        map_shuffle: Supports booleans (`True` -> dungeons shuffle, `False` -> none)
            or explicit mode names: none, overworld, dungeons,
            overworld_dungeons, everything.
        crest_shuffle: Whether crest links are shuffled.
        battlefield_shuffle: API compatibility parameter (accepted and forwarded).
        companion_shuffle: API compatibility parameter (accepted and forwarded).
        kaeli_mom: API compatibility parameter (accepted and forwarded).
    """

    _build_if_needed()

    cmd = [
        "dotnet",
        str(_DLL),
        str(seed),
        str(map_shuffle),
        _to_bool_str(crest_shuffle),
        _to_bool_str(battlefield_shuffle),
        _to_bool_str(companion_shuffle),
        _to_bool_str(kaeli_mom),
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "FFMQR rooms generation failed.\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )

    return completed.stdout


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate ffmqr rooms.yaml locally")
    parser.add_argument("seed")
    parser.add_argument("map_shuffle")
    parser.add_argument("crest_shuffle")
    parser.add_argument("battlefield_shuffle")
    parser.add_argument("companion_shuffle")
    parser.add_argument("kaeli_mom")

    args = parser.parse_args()

    print(
        generate_rooms_yaml(
            seed=args.seed,
            map_shuffle=args.map_shuffle,
            crest_shuffle=args.crest_shuffle,
            battlefield_shuffle=args.battlefield_shuffle,
            companion_shuffle=args.companion_shuffle,
            kaeli_mom=args.kaeli_mom,
        ),
        end="",
    )
