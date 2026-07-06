# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qungeon is a quantum puzzle game built with **pygame** and Google's **Unitary** library (`unitary.alpha`), which handles all quantum logic (state vectors, entanglement, measurement sampling). The player moves through grid-based levels and applies quantum gates (dragged from a hotbar) to pillar objects to collapse them out of the way and reach the END tile.

This is a fork (`chrishalkias/Qungeon`, upstream `IvorBr/Qungeon`) being further developed.

## Setup, Run, Test

Requires Python 3.8+. The project venv lives at `QungeonEnv/` in the repo root.

```bash
source QungeonEnv/bin/activate    # or create fresh: python3 -m venv QungeonEnv && pip install -r requirements.txt

python Qungeon.py        # start at level 1
python Qungeon.py 5      # start at a specific level (validated; bad numbers exit with a clean error)
```

Tests are standalone assert-based scripts (no pytest fixtures needed, though pytest also discovers them):

```bash
python tests/test_grouping.py            # pure Python, no game deps
python tests/test_level_validation.py    # pure Python, no game deps
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_walkability.py   # needs venv; headless
```

The game must be run from the repo root: all asset and level paths are relative (`./assets/...`, `./levels/...`). For headless runs (CI, agents), set `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`.

There is no linter config; `pylint`/`black` in the environment are transitive dependencies of `unitary`.

## Architecture

Entry point `Qungeon.py` defines the `Game` class: level loading, the event/render loop, player movement, and drag-and-drop dispatch. Everything else lives in `scripts/`:

- **`scripts/game_objects.py`** — the core module. Defines the `gates` dict (maps gate names `X`, `H`, `Z`, `RotY`, `CNOT`, `CHAD` to `unitary.alpha` effects), tile/pillar enums, and the sprite classes: `Tile`, `Player`, `LootableObject` (boxes that give gates), and `QuantumObject` (pillars). `QuantumObject` multiple-inherits from `pygame.sprite.Sprite` (via `BaseObject`) **and** `alpha.QuantumObject` — it is simultaneously a rendered sprite and a qubit registered in the game's `alpha.QuantumWorld` (`game.quantum_grid`). Also home to `exact_probability_zero()`, which computes exact P(|0⟩) by simulating the world's circuit with cirq (state-vector sim per call — fine at current level sizes, ≤15 qubits).
- **`scripts/level_validation.py`** — pure-Python (no pygame/unitary imports) validation for level JSON: `validate_level()`, `parse_pos()`, `LevelError`. All whitelists live here (`VALID_TILES`, `VALID_GATES`, `VALID_EFFECTS`) — extend `VALID_EFFECTS` if a new level needs an initial effect beyond `Flip`/`Superposition`/`Phase`.
- **`scripts/user_interface.py`** — `Hotbar` and `ItemSlot`: the gate inventory, drag-and-drop of gates onto pillars, hover previews. `Hotbar.remove_item` is where a dropped gate is actually applied (single-qubit gates apply immediately; control gates `CNOT`/`CHAD` instead start a second drag from the control pillar to the target pillar, handled in `Game.handle_object_dragging`).
- **`scripts/grouping_system.py`** — union-of-groups tracking of which pillars are entangled. Applying a controlled gate `join`s the two objects' groups; groups drive the entanglement hover-lines and the cycling correlation animation (`Game.correlation_update`, fired by a 1s `pygame.USEREVENT` timer). `Group.states` starts as `{}` and is populated on the first applied effect — keep it len()-safe.
- **`scripts/flip_phase.py`** — `FlipPhase`, a custom `QuantumEffect` (partial Y rotation) used for the `RotY` gate.
- **`scripts/common_functions.py`** — shared drag/hover/text helpers.

All modules are star-imported into `Qungeon.py`, so names like `alpha`, `BLOCK_SIZE`, `pillar_image`, and `TileType` are in its namespace via `scripts.game_objects`.

### Quantum state flow

`QuantumObject.apply_effect` (game_objects.py) is the heart of the game: it applies a unitary effect to the qubit, tracks Z-phase manually (`phase_Z` flag — Unitary doesn't expose phase directly), re-samples probabilities via `quantum_grid.get_probabilities(..., PEEK_COUNT)` (1000 shots) for the *display*, and maps the result to the pillar's tint: blue = |1⟩, white/transparent = pure |0⟩, red-ish = near |0⟩, green channel = Z-phase. **Walkability is separate from display**: a pillar is passable iff `exact_probability_zero()` ≥ 1 − 1e-9 (`QuantumObject.function`) — deterministic, computed from the exact state vector, not the sampled histogram. Controlled gates go through `alpha.quantum_if(control).apply(effect)(target)`.

### Level format

Levels are `levels/<N>.json`, validated by `validate_level()` **before** `clean_up()` (so a bad file never destroys the running game), then loaded by `Game.load_level`. Progression is sequential by number (`advance_level`); the game ends when `levels/<N+1>.json` doesn't exist, so keep numbering dense. Schema:

```json
{
  "tiles":            { "(x,y)": "START|EMPTY|END|WALL" },  // exactly one START required
  "objects":          { "(x,y)": "X" },          // lootable box containing a gate (must be in VALID_GATES)
  "quantum_objects":  [ "(x,y)" ],               // pillars, start in |0>
  "gates":            { "X": 1, "H": 2 },        // starting hotbar contents
  "effects":          [ { "position": "(x,y)", "effect": "Flip",
                          "target": "(x,y)" } ]  // initial state prep; "target" makes it controlled
}
```

Positions are parsed by `parse_pos()` (exactly two ints, no `eval`). Effect names must be in `VALID_EFFECTS` (`Flip`, `Superposition`, `Phase`). Malformed files raise `LevelError` naming the file and field. Test fixtures for malformed levels live in `tests/fixtures/`.

### Coordinate/key conventions

Grid coordinates are tile units; pixels = tile × `BLOCK_SIZE` (16px art × `SCALE_FACTOR` 4 = 64). Note the two keying schemes: `game.tiles` is keyed by `(x, y)` **tuples**, while `game.objects` is keyed by `"x,y"` **strings** (also used as the `alpha.QuantumObject` name). Keep this straight when adding lookups.

## Known Quirks (intentional or accepted — don't "fix" without deciding)

- **Phase tracking is a heuristic**: `phase_Z` in `apply_effect` is hand-tracked from pre-effect sampled states because Unitary doesn't expose phase. It drifts from physical truth in edge cases (X keeps the flag, RotY never touches it). Revisit only when a level depends on phase.
- **Controlled-gate targets have no adjacency check**: the player must be adjacent to the *control* pillar, but the target can be anywhere. Possibly intended (action at a distance) — decide before changing.
- **`hop_animation` blocks the event loop** (~100 ms per hop): held keys queue extra moves, QUIT is delayed. Harmless at current length.
- **Level validation checks schema, not JSON syntax or cross-references**: a file with broken JSON syntax raises `json.JSONDecodeError` (uncaught during R-restart), and an effect positioned on a non-pillar tile passes validation but crashes at load.
- **`requirements.txt` pins `unitary` to git `main`** (editable install) — upstream changes can break the game without local changes. Pin to a SHA when development gets serious.

Full audit history (10 tickets, all fixed and merged 2026-07-06): see `AUDIT.md`.

## Controls (for manual testing)

WASD move · Q quit · R restart level · drag gates from hotbar onto adjacent pillars · for CNOT/CHAD, drop the gate on the control pillar, then drag from control to target pillar · hover over a pillar to see entanglement lines (dark blue).
