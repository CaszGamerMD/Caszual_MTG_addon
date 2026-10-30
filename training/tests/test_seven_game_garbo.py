"""Seven-game Garbo/Wilds match requirements and policy isolation."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
from goblin_strategy import GarboPressurePolicy
from seven_game_garbo import run


class SevenGameMatchTests(unittest.TestCase):
    def test_seven_15_turn_games_alternating_seats_and_baseline_wilds(self):
        calls = []
        deck_a = {'sourceDeckId': 5254666, 'name': 'Garbo Gobbos'}
        deck_b = {'sourceDeckId': 5189995, 'name': 'Getting Wild'}

        def fake_diagnose(_rules, decks, seed, turns, policies):
            calls.append(dict(decks=decks, seed=seed, turns=turns, policies=policies))
            return dict(turnsStarted=[15, 15])

        def fake_adjudicate(_report, garbo_seat):
            return dict(outcome='win' if garbo_seat == 0 else 'loss',
                        winner=0, basis='turn_limit_life_score',
                        scores=[31, 21], invalidReasons=[])

        def fake_telemetry(_report):
            return dict(spellsCastBySeat=[5, 4], attacksBySeat=[6, 3],
                        openingMulligans=[0, 1], runtimeQuestionCount=0)

        with patch('seven_game_garbo._coverage', return_value=[]), \
             patch('seven_game_garbo.s.diagnose', side_effect=fake_diagnose), \
             patch('seven_game_garbo.gauntlet.adjudicate', side_effect=fake_adjudicate), \
             patch('seven_game_garbo.gauntlet.match_telemetry', side_effect=fake_telemetry):
            result = run(object(), deck_a, deck_b, seed=1200)

        self.assertEqual(len(calls), 7)
        self.assertEqual([r['seed'] for r in calls], list(range(1200, 1207)))
        self.assertTrue(all(r['turns'] == 15 for r in calls))
        self.assertEqual([r['garboFirst'] for r in result['matches']],
                         [True, False, True, False, True, False, True])
        for index, call in enumerate(calls):
            garbo_seat = index % 2
            self.assertEqual(call['decks'][garbo_seat]['sourceDeckId'], 5254666)
            self.assertEqual(call['decks'][1 - garbo_seat]['sourceDeckId'], 5189995)
            self.assertIsInstance(call['policies'][garbo_seat], GarboPressurePolicy)
            self.assertEqual(type(call['policies'][1 - garbo_seat]), s.Policy)
        self.assertEqual((result['garboWins'], result['wildsWins']), (4, 3))
        self.assertFalse(result['learningEligible'])
        self.assertEqual(result['firstPlayerSplit'], {'Garbo': 4, 'Wilds': 3})

    def test_fail_closed_on_unsupported_deck_or_wrong_window(self):
        garbo = {'sourceDeckId': 5254666}
        wilds = {'sourceDeckId': 5189995}
        with self.assertRaises(ValueError):
            run(object(), garbo, wilds, games=6)
        with self.assertRaises(ValueError):
            run(object(), garbo, wilds, turns=10)
        with patch('seven_game_garbo._coverage', side_effect=[['Unresolved'], []]):
            with self.assertRaises(ValueError):
                run(object(), garbo, wilds)

    def test_blocked_games_are_never_counted_as_wins(self):
        with patch('seven_game_garbo._coverage', return_value=[]), \
             patch('seven_game_garbo.s.diagnose',
                   return_value=dict(turnsStarted=[15, 15])), \
             patch('seven_game_garbo.gauntlet.adjudicate',
                   return_value=dict(outcome='blocked', winner=None, basis='invalid',
                                     scores=[30, 30], invalidReasons=['runtime_rules_question'])), \
             patch('seven_game_garbo.gauntlet.match_telemetry',
                   return_value=dict(spellsCastBySeat=[0, 0],
                                     attacksBySeat=[0, 0],
                                     openingMulligans=[0, 0], runtimeQuestionCount=1)):
            result = run(object(), {'sourceDeckId': 5254666},
                         {'sourceDeckId': 5189995})
        self.assertEqual(result['blocked'], 7)
        self.assertEqual(result['garboWins'], 0)
        self.assertEqual(result['wildsWins'], 0)
        self.assertIsNone(result['averageGarboLifeMargin'])


if __name__ == '__main__':
    unittest.main()
