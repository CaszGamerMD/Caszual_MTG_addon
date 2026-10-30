"""Garbo policy tests; decision hypotheses, not legal Commander certification."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
from goblin_strategy import GarboPressurePolicy
from strategy_lab import policy_for, run


def permanent(uid, power=0, toughness=0, kind='creature', creature=True, traits='',
              tapped=False, attached=None):
    return dict(id=uid, name=uid, kind=kind, isCreature=creature,
                power=power, toughness=toughness, traits=traits,
                tapped=tapped, fresh=False, attachedTo=attached)


def obs(actions, hand=(), board=(), enemy_board=(), enemy_life=40, turn=3, phase='main'):
    players = [dict(life=40, battlefield=list(board), commanderDamage={}),
               dict(life=enemy_life, battlefield=list(enemy_board), commanderDamage={})]
    return s.Observation(0, turn, phase, tuple(hand), json.dumps({'players': players}),
                         tuple(actions))


PASS = s.Candidate('pass', 'pass', features=s.features(**{'pass': 1}))


class GarboPolicyTests(unittest.TestCase):
    def test_only_garbo_gets_new_profile(self):
        self.assertEqual(policy_for('baseline').version, 0)
        self.assertIsInstance(policy_for('garbo-pressure'), GarboPressurePolicy)
        self.assertNotEqual(policy_for('garbo-pressure').scope, policy_for('baseline').scope)

    def test_prioritizes_a_second_land_over_early_creature(self):
        land = s.Card('l', 'Land', 'land', mask=8)
        goblin = s.Card('g', 'Unseen', 'creature', '{R}', power=2, toughness=2)
        candidates = [s.Candidate('l', 'land', 'l', s.features(power=1)),
                      s.Candidate('g', 'cast', 'g', s.features(power=2)), PASS]
        own = [permanent('a', kind='land', creature=False)]
        self.assertEqual(GarboPressurePolicy().choose(obs(candidates, (land, goblin), own)).kind,
                         'land')

    def test_tribal_creature_synergy_is_not_a_name_shortcut(self):
        goblin = s.EventDefinition('Unseen', frozenset({'Creature'}),
            frozenset({'Goblin'}), False, 1, 1, frozenset())
        creature = s.Card('g', 'Unseen', 'creature', '{1}{R}', power=1,
            toughness=1, event_definition=goblin)
        vanilla = s.Card('v', 'Vanilla', 'creature', '{2}', power=3, toughness=3)
        acts = [s.Candidate('g', 'cast', 'g', s.features(power=1)),
                s.Candidate('v', 'cast', 'v', s.features(power=3)), PASS]
        lands = [permanent(str(i), kind='land', creature=False) for i in range(4)]
        self.assertEqual(GarboPressurePolicy().choose(obs(acts, (creature, vanilla), lands)).card_id,
                         'g')

    def test_does_not_throw_creature_away_into_defender(self):
        attacker = permanent('a', 2, 1)
        blocker = permanent('b', 4, 4)
        attack = s.Candidate('atk', 'attack_group', features=s.features(damage=2, power=.2),
                             attack_ids=('a',))
        self.assertEqual(GarboPressurePolicy().choose(obs([attack, PASS], board=[attacker],
            enemy_board=[blocker], phase='attack')).kind, 'pass')

    def test_presses_unblocked_lethal_and_uses_menace(self):
        attacker = permanent('a', 5, 3)
        attack = s.Candidate('atk', 'attack_group', features=s.features(damage=5, lethal=1),
                             attack_ids=('a',))
        self.assertEqual(GarboPressurePolicy().choose(obs([attack, PASS], board=[attacker],
            enemy_life=5, phase='attack')).kind, 'attack_group')
        menace = permanent('m', 3, 3, traits='3;3;menace')
        one_blocker = permanent('b', 4, 4)
        attack2 = s.Candidate('atk2', 'attack_group', features=s.features(damage=3),
                             attack_ids=('m',))
        self.assertEqual(GarboPressurePolicy().choose(obs([attack2, PASS], board=[menace],
            enemy_board=[one_blocker], phase='attack')).kind, 'attack_group')

    def test_does_not_wipe_own_wide_board(self):
        wipe = s.Card('wipe', 'Wrath', 'removal_spell', '{2}{B}{B}',
                      removal='destroy_all_creatures')
        cast = s.Candidate('wipe', 'cast', 'wipe', s.features(power=4))
        our_army = [permanent(str(i), 1, 1) for i in range(6)]
        self.assertEqual(GarboPressurePolicy().choose(obs([cast, PASS], (wipe,), our_army,
            [permanent('enemy', 1, 1)])).kind, 'pass')

    def test_does_not_ping_pong_already_attached_equipment(self):
        board = [permanent('eq', kind='equipment', creature=False, attached='one'),
                 permanent('one', 3, 3), permanent('two', 2, 2)]
        equip = s.Candidate('equip', 'equip', 'eq', s.features(power=.5),
                            target_permanent='two')
        self.assertEqual(GarboPressurePolicy().choose(obs([equip, PASS], board=board)).kind,
                         'pass')

    def test_garbo_experiment_keeps_wilds_on_baseline(self):
        focal = dict(sourceDeckId=5189995)
        opponent = dict(sourceDeckId=5254666)
        matches = [dict(seed=100 + i, focalSeat=i % 2,
                        outcome='tie', winner=None, adjudication='turn_limit_life_score',
                        scores=[40, 40], turnsStarted=[10, 10], invalidReasons=[],
                        telemetry=dict(runtimeQuestionCount=0, landDropsBySeat=[3, 3],
                                       spellsCastBySeat=[2, 2], attacksBySeat=[1, 1],
                                       openingMulligans=[0, 0])) for i in range(2)]
        baseline = dict(engineCommit='head', matches=matches, coverage=[])
        seen = []
        def fake_diagnose(_rules, _decks, _seed, _turns, policies):
            seen.append(policies)
            return dict(turnsStarted=[10, 10])
        adjudication = dict(outcome='tie', winner=None, basis='turn_limit_life_score',
                            scores=[40, 40], invalidReasons=[])
        telemetry = matches[0]['telemetry']
        with patch('strategy_lab.subprocess.check_output', return_value='head\n'), \
             patch('strategy_lab.s.diagnose', side_effect=fake_diagnose), \
             patch('strategy_lab.gauntlet.adjudicate', return_value=adjudication), \
             patch('strategy_lab.gauntlet.match_telemetry', return_value=telemetry):
            outcome = run(object(), focal, opponent, baseline, games=2,
                          profile='garbo-pressure', seed=100)
        self.assertEqual(list(outcome['comparisons']), ['5254666'])
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(sum(isinstance(p, GarboPressurePolicy) for p in row) == 1
                            for row in seen))
        self.assertFalse(outcome['learningEligible'])


if __name__ == '__main__':
    unittest.main()
