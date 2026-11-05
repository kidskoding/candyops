"""Choose one bowl for a whole street: the candies that give the most kids a favorite they can eat."""

from __future__ import annotations

# Share of US children with each allergy (Gupta et al., Pediatrics 2018). Egg, wheat and soy are left out: their
# rates could not be confirmed from the published abstract.
PREVALENCE = {"peanut": 0.022, "milk": 0.019, "tree_nut": 0.012}


def kid_groups(prevalence: dict[str, float] = PREVALENCE) -> dict[str | None, float]:
    """Share of kids per group; None is a kid with none of the listed allergies.

    shortcut: treats each allergy as its own group, though about 40% of allergic kids have more than one; model
    combinations if a source gives their rates.
    """
    return {**prevalence, None: 1 - sum(prevalence.values())}


def expected_win(bowl: list[str], win: dict[str, float], safe: dict[str, set[str]],
                 groups: dict[str | None, float]) -> float:
    """Average, over kids, of the best win rate among the bowl's candies each kid can eat (0 when none)."""
    total = 0.0
    for allergy, share in groups.items():
        edible = [win[c] for c in bowl if allergy is None or c in safe[allergy]]
        total += share * max(edible, default=0.0)
    return total


def street_bowl(win: dict[str, float], safe: dict[str, set[str]], size: int = 10,
                groups: dict[str | None, float] | None = None) -> list[str]:
    """Greedy pick of `size` candies maximizing expected_win; each step adds the candy with the largest gain."""
    groups = groups or kid_groups()
    bowl: list[str] = []
    for _ in range(size):
        best = max((c for c in win if c not in bowl),
                   key=lambda c: (expected_win(bowl + [c], win, safe, groups), win[c], c))
        bowl.append(best)
    return bowl


def coverage(bowl: list[str], safe: dict[str, set[str]]) -> dict[str, int]:
    """How many candies in the bowl each allergic group can eat."""
    return {allergy: sum(c in candies for c in bowl) for allergy, candies in safe.items()}
