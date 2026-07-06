"""Runnable check for deterministic walkability (QUN-5).

Needs pygame + unitary + cirq, so it skips cleanly if they're unavailable.
Run with the project venv:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_walkability.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((800, 600))
    from Qungeon import Game
    from scripts.game_objects import gates
except Exception as exc:  # pragma: no cover - environment without deps
    print(f"SKIP test_walkability: {type(exc).__name__}: {exc}")
    sys.exit(0)


def test_pure_zero_is_passable():
    g = Game(argparse.Namespace(level=1))
    pillar = g.objects["5,4"]        # starts |1> (Flip in level 1)
    pillar.apply_effect(g, gates["X"])  # -> |0>
    assert pillar.function(g, 5, 4) is True


def test_roty_never_flips_passability_without_state_change():
    g = Game(argparse.Namespace(level=1))
    pillar = g.objects["5,4"]
    pillar.apply_effect(g, gates["RotY"])  # ~2/3 : 1/3, not pure |0>
    results = [pillar.function(g, 5, 4) for _ in range(25)]
    assert all(r is False for r in results), results  # deterministic, never passable


if __name__ == "__main__":
    test_pure_zero_is_passable()
    test_roty_never_flips_passability_without_state_change()
    print("walkability checks passed")
