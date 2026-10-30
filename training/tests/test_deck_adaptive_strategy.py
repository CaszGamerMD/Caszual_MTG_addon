"""Tests for one deck-driven strategy engine and public-state tactical switching."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
from deck_adaptive_strategy import AdaptiveDeckPolicy, DeckPlan, analyze_deck, tactical_mode
from seven_game_deck_adaptive import run


DECKS = Path(__file__).resolve().parents[1] / 'decks'


def permanent(uid, power=0, toughness=0, kind='creature', creature=True,
              tapped=False, fresh=False, traits=''):
    return dict(id=uid, name=uid, kind=kind, isCreature=creature,
                power=power, toughness=toughness, traits=traits,
                tapped=tapped, fresh=fresh)


def observation(actions=(), hand=(), own=(), enemies=(), life=40, enemy_life=40, turn=7,
                phase='main', seat=0):
    players = [dict(life=life, battlefield=list(own), commanderDamage={}),
               dict(life=enemy_life, battlefield=list(enemies), commanderDamage={})]
    if seat == 1:
        players.reverse()
    return s.Observation(seat,turn,phase,tuple(hand),
                         json.dumps(dict(players=players)),tuple(actions))


def raw(name, types, text='', subtypes=(), qty=1):
    return dict(name=name, types=types, subTypes=subtypes, manaCost='{2}',
                oracleText=text, quantity=qty)


class AdaptiveStrategyTests(unittest.TestCase):
    def test_real_deck_plans_derived_from_types_and_oracle_not_names(self):
        garbo = json.loads((DECKS / '5254666-garbo-gobbos.json').read_text())
        wilds = json.loads((DECKS / '5189995-enchantments.json').read_text())
        gp, wp = analyze_deck(garbo), analyze_deck(wilds)
        self.assertEqual((gp.primary, gp.secondary, gp.tribe),
                         ('tribal_swarm','token_swarm','Goblin'))
        self.assertEqual((wp.primary, wp.secondary), ('enchantment_value','lifegain'))
        # No deck id, deck label, source URL or enemy deck is used to choose a plan.
        renamed = dict(garbo, name='Different title', sourceDeckId=12345,
                       sourceUrl='https://example.com/unrelated')
        self.assertEqual(analyze_deck(renamed), gp)
        self.assertGreater(gp.metric('tribe_members'), 15)
        self.assertGreater(wp.metric('enchantment'), 30)

    def test_unseen_deck_can_infer_new_tribe_and_commander_payoff(self):
        deck = dict(commanders=[raw('Leader', ['Creature'], 'Other Faeries get +1/+1',
                                    ('Faerie',))],
                    mainboard=[raw('Unseen Soldier', ['Creature'], subtypes=('Faerie',),qty=20),
                               raw('Mystic', ['Sorcery'], qty=10)])
        plan = analyze_deck(deck)
        self.assertEqual(plan.tribe,'Faerie')
        self.assertEqual(plan.primary,'tribal_swarm')

    def test_tactical_modes_respond_to_opponent_and_rebuild(self):
        attackers = [permanent('a',5,5), permanent('b',4,4)]
        self.assertEqual(tactical_mode(observation(own=attackers, enemy_life=7)),
                         'finish')
        foes = [permanent('big',9,9)]
        self.assertEqual(tactical_mode(observation(own=attackers,enemies=foes,life=8)),
                         'stabilize')
        self.assertEqual(tactical_mode(observation(own=(),enemies=foes,turn=10)),
                         'develop')  # Only one enemy; don't overreact.
        self.assertEqual(tactical_mode(observation(own=(),enemies=foes+[permanent('c',2,2)],
                                                    turn=10)),
                         'rebuild')
        self.assertEqual(tactical_mode(observation(own=attackers,enemies=(),turn=6)),
                         'pressure')

    def test_adaptive_enchantment_deck_prefers_engine_piece(self):
        enchant=s.Card('e','Unknown Enchantment','enchantment','{2}')
        vanilla=s.Card('v','Unseen Creature','creature','{2}',power=1,toughness=1)
        actions=(s.Candidate('e','cast','e',s.features()),
                 s.Candidate('v','cast','v',s.features()),
                 s.Candidate('pass','pass',features=s.features(**{'pass': 1})))
        own=[permanent(f'l{i}',kind='land',creature=False) for i in range(4)]
        policy=AdaptiveDeckPolicy(plan=DeckPlan(primary='enchantment_value'))
        self.assertEqual(policy.choose(observation(actions,(enchant,vanilla),own,turn=5)).card_id,'e')

    def test_tribal_synergy_not_specific_to_goblin(self):
        faerie=s.EventDefinition('A Faerie',frozenset({'Creature'}),
            frozenset({'Faerie'}),False,1,1,frozenset())
        faerie_card=s.Card('f','Unknown','creature','{2}',power=1,toughness=1,
                           event_definition=faerie)
        vanilla=s.Card('v','Vanilla','creature','{2}',power=2,toughness=2)
        actions=(s.Candidate('f','cast','f',s.features(power=1)),
                 s.Candidate('v','cast','v',s.features(power=2)))
        policy=AdaptiveDeckPolicy(plan=DeckPlan(primary='tribal_swarm',tribe='Faerie'))
        own=[permanent(f'l{i}',kind='land',creature=False) for i in range(4)]
        self.assertEqual(policy.choose(observation(actions,(faerie_card,vanilla),own)).card_id,'f')

    def test_same_ai_uses_different_deck_plans_without_hidden_library(self):
        calls=[]
        g=dict(sourceDeckId=5254666, name='Garbo')
        w=dict(sourceDeckId=5189995, name='Wilds')
        def diagnose(_rules,decks,seed,turns,policies):
            calls.append(dict(decks=decks,seed=seed,turns=turns,policies=policies))
            return dict(turnsStarted=[15,15])
        with patch('seven_game_deck_adaptive._coverage',return_value=[]), \
             patch('seven_game_deck_adaptive.analyze_deck',side_effect=[
                 DeckPlan(primary='tribal_swarm',tribe='Goblin'),
                 DeckPlan(primary='enchantment_value')]), \
             patch('seven_game_deck_adaptive.s.diagnose',side_effect=diagnose), \
             patch('seven_game_deck_adaptive.gauntlet.adjudicate',
                   return_value=dict(outcome='tie',winner=None,basis='turn_limit_life_score',
                                     scores=[40,40],invalidReasons=[])), \
             patch('seven_game_deck_adaptive.gauntlet.match_telemetry',
                   return_value=dict(spellsCastBySeat=[0,0],attacksBySeat=[0,0],
                                     openingMulligans=[0,0],runtimeQuestionCount=0)):
            result=run(object(),g,w)
        self.assertEqual(len(calls),7)
        self.assertEqual(result['ties'],7)
        self.assertEqual(result['blocked'],0)
        self.assertEqual(result['plans']['Garbo']['primary'],'tribal_swarm')
        self.assertEqual(result['plans']['Wilds']['primary'],'enchantment_value')
        for i,call in enumerate(calls):
            seat=i%2
            a,b=call['policies']
            self.assertIs(type(a),AdaptiveDeckPolicy)
            self.assertIs(type(b),AdaptiveDeckPolicy)
            self.assertEqual(a.weights,b.weights)
            self.assertNotEqual(a.plan,b.plan)
            self.assertEqual(call['policies'][seat].plan.primary,'tribal_swarm')
            self.assertEqual(call['policies'][1-seat].plan.primary,'enchantment_value')
            self.assertEqual(call['turns'],15)

    def test_blocked_games_not_scored(self):
        with patch('seven_game_deck_adaptive._coverage',return_value=[]), \
             patch('seven_game_deck_adaptive.analyze_deck',return_value=DeckPlan()), \
             patch('seven_game_deck_adaptive.s.diagnose',
                   return_value=dict(turnsStarted=[15,15])), \
             patch('seven_game_deck_adaptive.gauntlet.adjudicate',
                   return_value=dict(outcome='blocked',winner=None,basis='invalid',
                                     scores=[40,40],invalidReasons=['runtime_rules_question'])), \
             patch('seven_game_deck_adaptive.gauntlet.match_telemetry',
                   return_value=dict(spellsCastBySeat=[0,0],attacksBySeat=[0,0],
                                     openingMulligans=[0,0],runtimeQuestionCount=1)):
            report=run(object(),dict(sourceDeckId=5254666),dict(sourceDeckId=5189995))
        self.assertEqual(report['blocked'],7)
        self.assertEqual((report['garboWins'],report['wildsWins']),(0,0))


if __name__ == '__main__':
    unittest.main()
