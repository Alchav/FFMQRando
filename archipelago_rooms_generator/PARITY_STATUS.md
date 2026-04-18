# FloorShuffling Parity Status (Python vs C#)

This tracks parity work between:

- C# source of truth: `FFMQRLib/gamelogic/FloorShuffling.cs`
- Python port: `archipelago_rooms_generator/rooms_generator.py`

## Snapshot

- **Overall estimate:** ~75-85% behavioral parity for typical seeds/modes.
- **Highest-risk remaining gap:** full `ClusterLocation`-based intradungeon validation/assembly loop.
- **Current expected user impact:** most seeds produce playable shuffles, but edge-case seeds may differ in structure/robustness from C#.

## What is now implemented in Python

### Data/schema alignment

- ✅ Current shuffling schema keys are consumed:
  - `priority_exits`
  - `no_exits`
  - `blocked_oneways`
  - `added_links`
  - pair-based `forced_links`

### Determinism and options

- ✅ Seed handling follows latest C# AP-style 8-char hex parsing and SHA-256 folding.
- ✅ Map-shuffle mode normalization includes latest textual aliases and ints.

### Core floor-link mechanics

- ✅ Entrance-pair logic links are built from `entrancespairs`.
- ✅ Forced links are connected early.
- ✅ Trigger-derived forbidden destinations are applied.
- ✅ Priority exits are preferred where applicable.

### Location-aware behavior

- ✅ Clusters receive location stamps from Subregion links.
- ✅ Intradungeon pre-pass now prioritizes same-location progress/deadend placement.
- ✅ Overworld reconnection prefers matching location links where possible.

### Crystal routing

- ✅ Non-intradungeon crystal handling includes:
  - special sky crystal placement step
  - explicit crystal deadend placement before generic deadends
  - location-aware origin preference with base-room fallback
- ✅ Crystal deadend placement stage now executes before generic deadend placement flow
  in the shared shuffle pipeline (with sky crystal excluded from deadend stage).

## Remaining gaps (ordered by impact)

### 1) Full `ClusterLocation` validation loop parity (HIGH)

**C# behavior:** intradungeon mode builds per-location candidate assemblies and retries until a valid configuration (including odd-link/no-exit constraints).  
**Python today:** location-aware pre-pass + generic fallback loops, but no full retry/validation model equivalent.

Likely effect:
- Some seeds that C# would restructure/retry may settle differently in Python.
- Edge-case robustness can diverge.

### 2) Exact overworld relinking semantics (MEDIUM-HIGH)

**C# behavior:** explicit `ConnectOverworldLink(...)` flow with location-sensitive decisions across fixed/switch groups and crystal source logic.  
**Python today:** location-preferred reconnection exists, but not all C# branching/fallback semantics are mirrored.

Likely effect:
- Region-to-overworld doorway mapping can differ while still being valid.

### 3) Error/retry behavior parity (MEDIUM)

**C# behavior:** targeted loops + explicit exception/dump paths in specific invalid states.  
**Python today:** selected loops still use bailout/fallback behavior to avoid hard failures.

Likely effect:
- Python may complete with a “best effort” topology where C# would continue searching or fail with diagnostics.

## Completion criteria for “full parity”

To claim full parity, all of the following should be true:

1. Implement `ClusterLocation`-equivalent intradungeon assembly/retry rules.
2. Port `ConnectOverworldLink` branching semantics end-to-end.
3. Align failure/diagnostic behavior for invalid placements.
4. Add cross-implementation fixture tests that compare Python output to C# output for a seed/mode matrix.

## Practical next step

Next highest-value coding step: port C# intradungeon `ClusterLocation` assembly loop (progress/deadend merge + odd/no-exit validation), then compare outputs on a seed matrix.
