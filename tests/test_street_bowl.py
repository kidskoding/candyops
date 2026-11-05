from candyops.street_bowl import coverage, expected_win, kid_groups, street_bowl

WIN = {"reeses": 84.0, "twix": 82.0, "snickers": 77.0, "skittles": 63.0, "starburst": 67.0}
SAFE = {"peanut": {"skittles", "starburst"}, "milk": {"skittles", "starburst"}, "tree_nut": {"skittles", "starburst"}}


def test_expected_win_gives_zero_to_kids_with_nothing_to_eat():
    groups = {"peanut": 0.5, None: 0.5}
    assert expected_win(["reeses"], WIN, SAFE, groups) == 0.5 * 84.0
    assert expected_win(["reeses", "starburst"], WIN, SAFE, groups) == 0.5 * 84.0 + 0.5 * 67.0


def test_street_bowl_adds_a_safe_candy_once_allergic_kids_matter():
    bowl = street_bowl(WIN, SAFE, size=2, groups={"peanut": 0.3, None: 0.7})
    assert set(bowl) == {"reeses", "starburst"}
    assert coverage(bowl, SAFE)["peanut"] >= 1


def test_kid_groups_sum_to_one():
    assert abs(sum(kid_groups().values()) - 1) < 1e-9
