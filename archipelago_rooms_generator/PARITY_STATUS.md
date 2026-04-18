# FloorShuffling Parity Status (Python vs C#)

This tracks parity work between:

- C# source of truth: `FFMQRLib/gamelogic/FloorShuffling.cs`
- Python port: `archipelago_rooms_generator/rooms_generator.py`

## Snapshot

- **Overall estimate:** ~85-92% behavioral parity for typical seeds/modes.
- **Highest-risk remaining gap:** error/retry behavior parity.
- **Current expected user impact:** most seeds produce playable shuffles; remaining divergence is primarily in edge-case failure/retry choices and diagnostics.

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
- ✅ Intradungeon same-location assembly now uses a per-origin retry loop that:
  - stages progress and deadend placement from location-matching clusters
  - propagates inherited restrictions while assembling a candidate
  - validates leftover link state before commit (no unresolved forced-deadend leftovers, even leftover link count)
  - commits pairings in batch only after a valid candidate is found
- ✅ Overworld reconnection now follows explicit branch ordering across switch/fixed pools with:
  - crystal-source location preference
  - preferred-origin entrance matching
  - location-aware fallback ordering

### Crystal routing

- ✅ Non-intradungeon crystal handling includes:
  - special sky crystal placement step
  - explicit crystal deadend placement before generic deadends
  - location-aware origin preference with base-room fallback
- ✅ Crystal deadend placement stage now executes before generic deadend placement flow
  in the shared shuffle pipeline (with sky crystal excluded from deadend stage).

## Remaining gaps (ordered by impact)

### 1) Error/retry behavior parity (MEDIUM)

**C# behavior:** targeted loops + explicit exception/dump paths in specific invalid states.  
**Python today:** selected loops still use bailout/fallback behavior to avoid hard failures.

Likely effect:
- Python may complete with a “best effort” topology where C# would continue searching or fail with diagnostics.

## Completion criteria for “full parity”

To claim full parity, all of the following should be true:

1. Align failure/diagnostic behavior for invalid placements.
2. Add cross-implementation fixture tests that compare Python output to C# output for a seed/mode matrix.

## Practical next step

Next highest-value coding step: align C#-style failure/retry/diagnostic behavior, then add cross-implementation seed-matrix fixture comparisons.
