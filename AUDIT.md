# Qungeon Codebase Audit — Bug Report & Tickets

Audit date: 2026-07-06. Scope: all Python in repo root + `scripts/`, all `levels/*.json`, README.
Each ticket is self-contained (context, repro, fix, acceptance criteria) so it can be handed to a subagent independently. Severity: P1 = crashes now, P2 = latent crash / wrong behavior, P3 = robustness/UX, P4 = cleanup/docs.

Verification note for all tickets: there is no test suite. Minimum verification = run `python Qungeon.py <level>` from repo root and exercise the repro steps. Where a ticket says "add a check", one small `test_*.py` or `assert`-based script is enough — no framework setup.

---

## QUN-1 (P1) — Pressing R crashes: restart loads `.txt` instead of `.json`

**File:** `Qungeon.py:276` (`Game.handle_keydown`)

```python
self.load_level(f"./levels/{self.current_level}.txt")
```

Level files are `.json` (see `load_level` call in `__init__`, line 61, and `advance_level`, line 163). Pressing R raises `FileNotFoundError`. README documents R as the restart key, so this is a shipped-but-broken feature.

**Repro:** `python Qungeon.py`, press R → crash.
**Fix:** change `.txt` → `.json`.
**Accept:** pressing R reloads the current level with fresh pillar states and the original hotbar; no crash on any level 1–8.

---

## QUN-2 (P1) — Pressing I crashes: `import_level()` does not exist

**File:** `Qungeon.py:277-278` (`Game.handle_keydown`)

```python
elif event.key == K_i:
    self.import_level()
```

No `import_level` method is defined anywhere → `AttributeError` on keypress.

**Repro:** run game, press I → crash.
**Fix:** delete the `K_i` branch (feature was never implemented). Do not stub it out.
**Accept:** pressing I does nothing; grep confirms no reference to `import_level` remains.

---

## QUN-3 (P2) — Latent crash: `correlation_update` calls `len(None)` for pillars with no initial effect

**Files:** `Qungeon.py:214-223` (`correlation_update`), `scripts/grouping_system.py:6` (`Group.states = None`), `scripts/game_objects.py:94-148`

`Group.states` starts as `None` and is only assigned inside `QuantumObject.apply_effect` **when an effect is passed** (`game_objects.py:137-138`). `correlation_update` runs every 1 s (USEREVENT timer, `Qungeon.py:55`) and does `if len(group.states) > 1:` — `TypeError: object of type 'NoneType' has no len()` for any group whose pillar never received an effect.

It doesn't fire today only by luck: every `quantum_objects` entry in levels 1–8 also appears in that level's `effects` list (verified). **Any new level with an un-initialized pillar crashes 1 second after loading.** Since this repo is being actively extended with new levels, this will bite.

**Repro:** add a level with a pillar in `quantum_objects` but no matching `effects` entry; load it; wait 1 s.
**Fix (pick the lazy one):** initialize `self.states = {}` in `Group.__init__` instead of `None`, or guard with `if group.states and len(group.states) > 1:`.
**Accept:** a level with an effect-less pillar runs for >5 s without crash; existing levels' entanglement color-cycling still works (level 8 after applying CNOTs shows cycling).

---

## QUN-4 (P2) — Grouping system and effect history never reset between levels

**File:** `Qungeon.py:106-114` (`clean_up`)

`clean_up` clears tiles, objects, sprites, hotbar, and `quantum_grid`, but **not** `self.grouping_system.groups`, `self.grouping_system.count`, or `self.effect_history`. Consequences:

- Stale `Group`s from previous levels survive; `correlation_update` keeps iterating them every second, calling `change_color` on killed sprites — wasted work and an unbounded leak across level transitions.
- `effect_history` grows forever across levels (it is also currently write-only — see QUN-9).

**Repro:** add `print(len(self.grouping_system.groups))` in `correlation_update`, play from level 1 to 3; count never drops on level change.
**Fix:** in `clean_up`, add `self.grouping_system.groups.clear()`, reset `self.grouping_system.count = 0`, and `self.effect_history.clear()`.
**Accept:** after `advance_level`, group count equals the new level's pillar count; no references to prior-level `QuantumObject`s remain in `grouping_system.groups`.

---

## QUN-5 (P2) — Walkability compares a *sampled* probability to exactly 1.0

**Files:** `scripts/game_objects.py:150-153` (`QuantumObject.function`), `game_objects.py:113,140-141` (`get_probabilities(..., PEEK_COUNT)` with PEEK_COUNT = 1000)

A pillar is passable iff `states[0] == 1.0`, where `states` comes from a 1000-shot sample. Two failure modes:

1. A state genuinely close to |0⟩ but not pure (e.g. after `RotY`, amplitudes like 2/3 : 1/3) can randomly sample 1000/1000 zeros → pillar becomes passable when the puzzle designer intended it blocked. Probability is small per-sample but nonzero and re-rolled on every `apply_effect`.
2. Conversely the color display (red = "very close to |0⟩" per README) suggests near-|0⟩ matters, but gameplay is a hard exact-1.0 check — visual and mechanical rules disagree.

Also note `states` is only refreshed inside `apply_effect`, so the walkability check reads whatever was sampled at the *last* gate application, not the current state (fine today since state only changes via gates, but a trap for future mechanics).

**Fix:** decide the rule and make it deterministic. Laziest correct option: keep "must be exactly |0⟩" but test it deterministically — e.g. threshold `states[0] >= 0.999` is still sampling-fragile; better is to track puriy via the already-sampled histogram AND increase confidence (`PEEK_COUNT` up) *or* use `quantum_grid` amplitudes if unitary exposes them. At minimum document the chosen rule in CLAUDE.md.
**Accept:** a written rule for "passable" exists; repeated gate applications on a RotY-rotated pillar never flip its passability without a state change; level 1–8 solutions still work.

---

## QUN-6 (P2) — Level loading has no validation (and uses `eval` on level data)

**File:** `Qungeon.py:63-104` (`load_level`), `scripts/user_interface.py:27-51` (`ItemSlot` hover)

Levels are external data files (input boundary) parsed with zero validation:

- Positions parsed with `eval(pos_str)` (lines 71, 81, 88, 97, 101) and effects resolved with `getattr(alpha, ...)` (line 98) — a malformed or malicious level file executes arbitrary code. For a game that will presumably accept community/custom levels, replace `eval` with a tuple parse (`tuple(int(v) for v in pos.strip("() ").split(","))`) and whitelist effect names against a dict.
- No START tile → `self.player` stays `None` (first load) → `AttributeError` in `display_game`. Multiple STARTs → last one silently wins.
- An item name not in `gates`/`gate_info_image` (e.g. a typo'd box item) creates an `ItemSlot` with `effect=None` and **no `hover_image` attribute** → hovering that slot crashes (`ItemSlot.hover`, `user_interface.py:46-51`); dropping it on a pillar silently consumes it with no effect.
- Missing JSON keys (`tiles`, `gates`, …) → raw `KeyError`. Note `clean_up()` runs *before* parsing, so a malformed file also destroys the current game state on a failed load (relevant once QUN-1's restart works).

**Fix:** one `validate_level(level_data)` function called at the top of `load_level` before `clean_up()`: required keys present, exactly one START, all positions parse as 2-int tuples, all gate/item/effect names in a whitelist. Fail with a clear message naming the file and field. Replace `eval` per above.
**Accept:** loading each malformed fixture (no START, bad position string, unknown gate, missing key) prints a clear error without crashing mid-load or clobbering current state; levels 1–8 load unchanged; `grep -n "eval(" Qungeon.py` returns nothing.

---

## QUN-7 (P3) — Entanglement lines are white on a white background

**File:** `Qungeon.py:18` (`SCREEN_BG_COLOR = (255, 255, 255)`) and `Qungeon.py:235` (`pygame.draw.line(self.screen, (255, 255, 255), ...)`)

Hover-lines between entangled pillars are drawn in pure white, and the screen background is pure white. The line is only visible where it happens to cross a textured tile; across background it's invisible. README advertises this feature ("lines will be drawn towards the entangled objects").

**Repro:** level 8, entangle diagonal-ish pillars after CNOT, hover — line segments off-tile are invisible.
**Fix:** one-line color change to something dark, e.g. `(60, 60, 200)`.
**Accept:** hovering an entangled pillar in level 8 shows a continuous visible line to its partner over both tiles and background.

---

## QUN-8 (P3) — Unvalidated CLI level argument crashes on startup

**File:** `Qungeon.py:281-287`

`python Qungeon.py 99` → `FileNotFoundError` traceback from `load_level`. Also negative/zero accepted.

**Fix:** after parsing args, check `os.path.isfile(f"./levels/{args.level}.json")`; if not, exit with `parser.error(f"level {args.level} does not exist")`.
**Accept:** `python Qungeon.py 99` prints a one-line error, exit code ≠ 0, no traceback; `python Qungeon.py 3` still works.

---

## QUN-9 (P4) — Dead and inconsistent code (single cleanup pass)

Bundle of small items, one ticket, one PR:

1. **`effect_history` is write-only** — appended in `apply_effect` (`game_objects.py:135`), never read, never cleared (see QUN-4). Either delete it or leave with a `# used by future undo feature` comment if that's planned.
2. **`TileType.DEL`** (`game_objects.py:52`) — defined, renders as a normal tile, no behavior, unused by any level. Delete or implement.
3. **`Hotbar.handle_mouse_up(self)`** placeholder (`user_interface.py:118-120`) conflicts with override `GameHotbar.handle_mouse_up(self, game, event)` (`Qungeon.py:28`) — different signatures, base is dead code. Delete the base method.
4. **`Tile.__init__` unbound-variable trap** (`game_objects.py:157-170`): `if type:` guards the image selection but `image` is used unconditionally after; `type=None` would raise `NameError` (Enum members are always truthy, so the guard does nothing today). Drop the `if type:` guard entirely.
5. **`QuantumObject.control` set dynamically** (`user_interface.py:111`), read in `Qungeon.py:205-208`. Initialize `self.control = None` in `QuantumObject.__init__` so the attribute always exists.
6. **Two keying schemes**: `game.tiles` keyed by `(x, y)` tuples, `game.objects` keyed by `"x,y"` strings. Pick one (tuples) — mechanical refactor, touches `Qungeon.py` and `game_objects.py` lookups. Optional; if skipped, leave as documented in CLAUDE.md.

**Accept:** game plays levels 1–8 identically after cleanup; grep confirms removed symbols are gone.

---

## QUN-10 (P4) — README errors

**File:** `README.md`

1. Line 16: `source Qungeon/bin/activate` — wrong path; the env created on line 15 is `QungeonEnv`, so it should be `source QungeonEnv/bin/activate`.
2. Controls section omits Q (quit) — bound in `handle_keydown` (`Qungeon.py:270`).
3. Controls section documents R (restart) which is currently broken — fixed by QUN-1; no README change needed once that lands.

**Accept:** copy-pasting the README setup block into a fresh shell produces a working env; controls list matches `handle_keydown` bindings.

---

## Notes (no ticket — design observations for whoever picks this up)

- **Phase tracking is a heuristic**: `phase_Z` in `apply_effect` (`game_objects.py:120-125`) is hand-tracked from *pre-effect* sampled states because Unitary doesn't expose phase. It's an approximation (e.g. X on a superposed state keeps the flag, RotY never touches it). Fine for current puzzles; will drift from physical truth if levels get phase-sensitive. Revisit only when a level actually depends on it.
- **Controlled-gate targets have no adjacency check**: dropping CNOT/CHAD requires the player adjacent to the *control* pillar (`user_interface.py:108`) but the target can be anywhere on screen. May be intended (quantum action at a distance!) — decide and either enforce `player.distance` on the target too, or document it as a mechanic.
- **`hop_animation` blocks the event loop** (`Qungeon.py:116-126`): during the ~100 ms hop, no events are processed — held keys queue extra moves and QUIT is delayed. Harmless at current animation length; fix only if animations get longer.
- **Sequential level discovery** (`advance_level`) means a gap in level numbering silently ends the game ("Game completed!"). Keep numbering dense.
- **requirements.txt pins `unitary` to git `main`** (editable): upstream changes can break the game without any local change. When development gets serious, pin to a commit SHA.
