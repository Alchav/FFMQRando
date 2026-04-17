# Local Archipelago rooms.yaml generator

This folder contains a local replacement for the old FFMQR web API endpoint that returned a generated `rooms.yaml`.

## Import from Python

```python
from ffmqr_rooms_generator import generate_rooms_yaml

rooms_yaml = generate_rooms_yaml(
    seed=123456,
    map_shuffle=True,
    crest_shuffle=False,
    battlefield_shuffle=True,
    companion_shuffle=True,
    kaeli_mom=False,
)
```

## Notes

- `map_shuffle` accepts:
  - booleans (`True` = dungeon floor shuffle, `False` = no floor shuffle), or
  - strings: `none`, `overworld`, `dungeons`, `overworld_dungeons`, `everything`.
- The module builds the bundled C# helper once (`dotnet build -c Release`) and then invokes it.
- Parameters `battlefield_shuffle`, `companion_shuffle`, and `kaeli_mom` are accepted for API compatibility.
