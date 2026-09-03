import math, unittest
from tennis_markov import game_win, tb_win, match_win, set_dist, solve_d, prob_at


class TestMarkov(unittest.TestCase):
    def test_deuce_closed_form(self):
        p = 0.6
        self.assertAlmostEqual(game_win(p, 3, 3), p * p / (p * p + (1 - p) ** 2))
        # advantage-in then deuce again must be consistent
        self.assertAlmostEqual(game_win(p, 4, 3), p + (1 - p) * game_win(p, 3, 3))

    def test_game_symmetry(self):
        self.assertAlmostEqual(game_win(0.5), 0.5)
        self.assertAlmostEqual(game_win(0.6) + game_win(0.4), 1.0)

    def test_tiebreak_5_8_from_brief(self):
        # coin-flip points: (1+6)/64 = 10.9375%
        self.assertAlmostEqual(tb_win(0.5, 0.5, 10, 5, 8, 0), 7 / 64)
        # realistic serve rotation, brief says 8-12% depending on server
        lo = tb_win(0.64, 0.64, 10, 5, 8, 1)
        hi = tb_win(0.64, 0.64, 10, 5, 8, 0)
        self.assertTrue(0.07 < min(lo, hi) < max(lo, hi) < 0.13, (lo, hi))

    def test_tiebreak_terminal_and_symmetry(self):
        self.assertEqual(tb_win(0.6, 0.6, 7, 7, 5, 0), 1.0)
        self.assertEqual(tb_win(0.6, 0.6, 7, 5, 7, 0), 0.0)
        self.assertAlmostEqual(tb_win(0.6, 0.6, 7, 0, 0, 0) + tb_win(0.6, 0.6, 7, 0, 0, 1), 1.0)

    def test_match_symmetry_and_monotone(self):
        self.assertAlmostEqual(match_win(0.64, 0.64, 5, server=0) + match_win(0.64, 0.64, 5, server=1), 1.0)
        self.assertGreater(match_win(0.66, 0.62, 5), match_win(0.64, 0.64, 5))
        self.assertGreater(match_win(0.64, 0.64, 5, sets=(1, 0)), match_win(0.64, 0.64, 5))
        self.assertGreater(match_win(0.64, 0.64, 5, sets=(1, 1), games=(5, 4), server=0),
                           match_win(0.64, 0.64, 5, sets=(1, 1), games=(4, 5), server=1))

    def test_set_dist_sums_to_one(self):
        for st in [(0, 0), (3, 3), (5, 6), (6, 6)]:
            self.assertAlmostEqual(sum(set_dist(0.65, 0.6, *st, server=1)), 1.0)

    def test_break_point_state(self):
        # A serving at 30-40 (pts A=2,B=3): probability should be lower than at 0-0
        base = match_win(0.64, 0.64, 5, sets=(0, 1), games=(2, 2), server=0)
        bp = match_win(0.64, 0.64, 5, sets=(0, 1), games=(2, 2), server=0, pts=(2, 3))
        self.assertLess(bp, base)

    def test_solve_d_roundtrip(self):
        d = 0.08
        p = prob_at("ATP", d, 5, server=None)
        self.assertAlmostEqual(solve_d("ATP", 5, p, server=None), d, places=5)

    def test_best_of_five_favors_favorite(self):
        self.assertGreater(prob_at("ATP", 0.05, 5, server=None), prob_at("ATP", 0.05, 3, server=None))


if __name__ == "__main__":
    unittest.main()
