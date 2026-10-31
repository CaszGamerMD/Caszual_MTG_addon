"""Planeswalker starting loyalty, ability cost, priority, and safe Oracle coverage."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from planeswalker_loyalty import compile_card,inspect_card
from planeswalker_runtime import legal,activate

ORACLE="+1: Draw a card.\n−2: Create a 1/1 blue Illusion creature token."
UNSUPPORTED="+1: Draw a card.\n−7: You get an emblem with an unknown rule."

class PlaneswalkerFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()
    def raw(self,text=ORACLE,loyalty='3',name='Unseen Planeswalker'):
        return dict(name=name,layout='normal',types=['Planeswalker'],
                    superTypes=['Legendary'],subTypes=['Test'],colors=['Blue'],
                    manaCost='{2}{U}',oracleText=text,loyalty=loyalty)
    def card(self,raw=None):
        return s.import_diagnostic_card(self.rules,raw or self.raw(),0,
                                         'unknown-planeswalker',{'Blue'})
    def setup_sim(self,loyalty='3'):
        pw=self.card(self.raw(loyalty=loyalty))
        self.assertEqual(pw.kind,'planeswalker')
        lands=[s.Card('pw-land-'+str(i),'Pw Land','land',mask=63) for i in range(6)]
        sim=s.Simulator(self.rules,23,
              decks=(s.demo_deck(0)+[pw]+lands,s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        player=sim.players[0]
        for card in [pw]+lands:
            (player.hand if card in player.hand else player.library).remove(card)
        player.hand.append(pw)
        player.battlefield.extend(s.Permanent(card) for card in lands)
        sim.cast_spell(0,pw)
        while sim.stack.items:sim.pass_priority(sim.stack.priority)
        on_board=next(x for x in player.battlefield if x.card.id==pw.id)
        return sim,pw,on_board
    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_parser_requires_entire_card_and_real_loyalty(self):
        result=compile_card(self.raw())
        self.assertEqual(result.starting_loyalty,3)
        self.assertEqual([x.delta for x in result.abilities],[1,-2])
        self.assertEqual([x.program.blocks[0].operation for x in result.abilities],
                         ['draw_cards','create_tokens'])
        self.assertIsNotNone(compile_card(self.raw(name='Another unknown planeswalker')))
        for raw in [self.raw(loyalty=None),self.raw(loyalty='*'),
                    self.raw(loyalty='-3'),self.raw(text=UNSUPPORTED),
                    self.raw(text=ORACLE+'\nThis creature has flying.')]:
            with self.subTest(raw=raw):
                self.assertIsNone(compile_card(raw))
                self.assertEqual(self.card(raw).kind,'unsupported')

    def test_enter_with_printed_loyalty_and_stack_draw(self):
        sim,pw,item=self.setup_sim()
        self.assertEqual(item.loyalty,3)
        before=len(sim.players[0].library)
        activation=activate(sim,0,pw.id,0)
        self.assertEqual(item.loyalty,4)
        self.assertEqual(len(sim.players[0].library),before)
        self.assertEqual(activation.payload[0]['operation'],'loyalty_ability')
        self.assertEqual(activation.payload[0]['sourceType'],'Planeswalker')
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),before-1)
        self.assertFalse(legal(sim,0))
        sim.invariant()

    def test_minus_two_token_and_restricted_loyalty_reuse(self):
        sim,pw,item=self.setup_sim()
        activate(sim,0,pw.id,1)
        self.assertEqual(item.loyalty,1)
        self.drain(sim)
        tokens=[x for x in sim.players[0].battlefield if x.card.is_token]
        self.assertEqual(len(tokens),1)
        self.assertEqual((tokens[0].card.power,tokens[0].card.toughness),(1,1))
        self.assertEqual(tokens[0].card.event_definition.subtypes,frozenset({'Illusion'}))
        self.assertFalse(legal(sim,0))
        sim.invariant()

    def test_timing_and_insufficient_loyalty_leave_no_side_effects(self):
        sim,pw,item=self.setup_sim('1')
        with self.assertRaises(ValueError):activate(sim,0,pw.id,1)
        self.assertEqual(item.loyalty,1)
        self.assertFalse(sim.stack.items)
        sim.phase='attack'
        with self.assertRaises(ValueError):activate(sim,0,pw.id,0)
        sim.phase='main'
        sim.stack.priority=1
        with self.assertRaises(ValueError):activate(sim,0,pw.id,0)
        sim.stack.priority=0
        self.assertTrue(legal(sim,0))
        sim.invariant()

    def test_loyalty_cost_zero_removes_source_not_ability(self):
        sim,pw,item=self.setup_sim('2')
        ability=activate(sim,0,pw.id,1)
        self.assertEqual(item.loyalty,0)
        self.assertNotIn(item,sim.players[0].battlefield)
        self.assertIn(pw,sim.players[0].graveyard)
        self.assertIn(ability,sim.stack.items)
        self.drain(sim)
        self.assertTrue(any(x.card.is_token for x in sim.players[0].battlefield))
        sim.invariant()

    def test_countered_loyalty_ability_cost_not_refunded(self):
        sim,pw,item=self.setup_sim()
        ability=activate(sim,0,pw.id,0)
        self.assertEqual(item.loyalty,4)
        before=len(sim.players[0].library)
        self.assertIsNotNone(sim.counter_stack_item(ability))
        self.assertFalse(sim.stack.items)
        self.assertEqual(item.loyalty,4)
        self.assertEqual(len(sim.players[0].library),before)
        self.assertFalse(legal(sim,0))
        sim.invariant()

    def test_real_deck_planeswalkers_are_not_promoted_by_partial_grammar(self):
        kaito=self.raw("At the beginning of your end step, if Kaito entered this turn, he phases out.\n+1: Draw a card. Then discard a card unless you attacked this turn.\n−2: Create a 1/1 blue Ninja creature token with \"This token can't be blocked.\"\n−7: You get an emblem with \"Whenever a creature you control deals combat damage to a player, search your library for a blue or black creature card, put it onto the battlefield, then shuffle.\"",loyalty=None,name='Kaito Shizuki')
        liliana=self.raw("+1: Up to one target creature gets -2/-1 until your next turn.\n−2: Mill two cards, then you may return a creature card from your graveyard to your hand.\n−7: You get an emblem with \"At the beginning of your end step, create X 2/2 black Zombie creature tokens, where X is two plus the number of Zombies you control.\"",loyalty=None,name='Liliana, the Last Hope')
        for card in (kaito,liliana):
            with self.subTest(name=card['name']):
                self.assertFalse(inspect_card(card)['executionReady'])
                self.assertEqual(self.card(card).kind,'unsupported')

if __name__=='__main__':unittest.main()
