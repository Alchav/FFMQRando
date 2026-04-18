# FloorShuffling Parity Status (Python vs C#)

This tracks parity work between:

- C# source of truth: `FFMQRLib/gamelogic/FloorShuffling.cs`
- Python port: `archipelago_rooms_generator/rooms_generator.py`

## Snapshot

- **Overall estimate:** ~90-95% behavioral parity for typical seeds/modes.
- **Highest-risk remaining gap:** cross-implementation output fixture coverage.
- **Current expected user impact:** generation behavior is closely aligned; remaining confidence work is primarily verification breadth rather than known algorithmic gaps.

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

### 1) Cross-implementation fixture matrix coverage (LOW-MEDIUM)

**Status:** parity logic work is implemented for current tracked items; remaining work is expanding regression confidence via seed/mode fixture comparisons against C# outputs.

## Completion criteria for “full parity”

To claim full parity, all of the following should be true:

1. Align failure/diagnostic behavior for invalid placements.
2. Add cross-implementation fixture tests that compare Python output to C# output for a seed/mode matrix.

> Note: item (1) is now substantially implemented in floor-shuffle retry/diagnostic paths; fixture coverage remains the primary completion blocker.

## Practical next step

Next highest-value coding step: add cross-implementation seed-matrix fixture comparisons and use them to validate any remaining edge-case branch differences.
