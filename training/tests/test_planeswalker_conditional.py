"""Generic Kaito-style loyalty effects, excluding unsupported phasing and emblems."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from planeswalker_conditional import compile_ability
from planeswalker_loyalty import compile_card
from planeswalker_runtime import activate

PARTIAL=(
    '+1: Draw a card. Then discard a card unless you attacked this turn.\n'
    '−2: Create a 1/1 blue Ninja creature token with "This token can\x27t be blocked."'
)
FULL=(
    'At the beginning of your end step, if Kaito entered this turn, he phases out.\n'
    + PARTIAL + '\n'
    '−7: You get an emblem with "Whenever a creature you control deals combat damage '
    'to a player, search your library for a blue or black creature card, put it '
    'onto the battlefield, then shuffle."'
)

class ConditionalLoyaltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def raw(self,oracle=PARTIAL,name='Unknown Shadow Planeswalker'):
        return dict(name=name,types=['Planeswalker'],superTypes=['Legendary'],
                    subTypes=['Shadow'],layout='normal',manaCost='{1}{U}{B}',
                    colors=['Blue','Black'],loyalty='3',oracleText=oracle)

    def fixture(self,oracle=PARTIAL):
        pw=s.import_diagnostic_card(self.rules,self.raw(oracle),0,'shadow-pw',{'Blue','Black'})
        self.assertEqual(pw.kind,'planeswalker')
        lands=[s.Card('shadow-land-'+str(i),'Source','land',mask=63) for i in range(6)]
        blocker=s.Card('shadow-blocker','Opponent blocker','creature',
                       power=2,toughness=2,traits='2;2;',
                       event_definition=s.EventDefinition('Opponent blocker',
                            frozenset({'Creature'}),frozenset(),False,2,2,frozenset()))
        sim=s.Simulator(self.rules,91,decks=(s.demo_deck(0)+[pw]+lands,
                                              s.demo_deck(1)+[blocker]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True
        sim.phase='main'
        a,b=sim.players
        for card in [pw]+lands:
            (a.hand if card in a.hand else a.library).remove(card)
        (b.hand if blocker in b.hand else b.library).remove(blocker)
        a.hand.append(pw);a.battlefield.extend(s.Permanent(card) for card in lands)
        defending=s.Permanent(blocker);b.battlefield.append(defending)
        sim.cast_spell(0,pw)
        self.drain(sim)
        return sim,pw,next(item for item in a.battlefield if item.card.id==pw.id),defending

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_generic_parser_and_whole_card_fail_closed(self):
        p=compile_card(self.raw())
        self.assertEqual([a.effect_kind for a in p.abilities],
                         ['draw_conditional_discard','unblockable_tokens'])
        self.assertEqual(p.abilities[1].program.token.keywords,frozenset({'unblockable'}))
        self.assertEqual(compile_card(self.raw(name='Another unfamiliar walker')),p)
        self.assertIsNone(compile_card(self.raw(FULL)))
        for bad in (
            PARTIAL.replace('unless you attacked this turn','unless it is your turn'),
            PARTIAL.replace('can\x27t be blocked','can be blocked'),
            PARTIAL.replace('Draw a card','Draw two cards and gain 3 life'),
            PARTIAL+' Then create a Treasure token.'
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(compile_card(self.raw(bad)))
        self.assertIsNone(compile_ability('Draw a card. Then win the game.'))

    def test_plus_one_draw_then_discard_when_no_attack(self):
        sim,pw,source,_=self.fixture()
        before=len(sim.players[0].library)
        hand_before=len(sim.players[0].hand)
        frame=activate(sim,0,pw.id,0)
        self.assertEqual(source.loyalty,4)
        self.assertEqual(len(sim.players[0].library),before)
        self.assertEqual(len(sim.players[0].hand),hand_before)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),before-1)
        self.assertEqual(len(sim.players[0].hand),hand_before)
        self.assertTrue(any(e['kind']=='loyalty_discard' for e in sim.events))
        self.assertFalse(any(e['kind']=='loyalty_discard_skipped' for e in sim.events))
        sim.invariant()

    def test_plus_one_keeps_draw_when_attacked(self):
        sim,pw,_,_=self.fixture()
        sim.attacked_this_turn.add(0)
        before=len(sim.players[0].library)
        hand_before=len(sim.players[0].hand)
        activate(sim,0,pw.id,0)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),before-1)
        self.assertEqual(len(sim.players[0].hand),hand_before+1)
        self.assertTrue(any(e['kind']=='loyalty_discard_skipped'
                            and e['details']['attacked'] for e in sim.events))
        sim.invariant()

    def test_minus_two_makes_unblockable_ninja(self):
        sim,pw,source,blocker=self.fixture()
        frame=activate(sim,0,pw.id,1)
        self.assertEqual(source.loyalty,1)
        self.assertEqual(len([x for x in sim.players[0].battlefield if x.card.is_token]),0)
        self.drain(sim)
        token=next(x for x in sim.players[0].battlefield if x.card.is_token)
        self.assertEqual((token.card.power,token.card.toughness),(1,1))
        self.assertEqual(token.card.event_definition.subtypes,frozenset({'Ninja'}))
        self.assertIn('unblockable',token.card.event_definition.abilities)
        self.assertFalse(sim.can_block(token,blocker))
        sim.invariant()

    def test_ordinary_creature_still_blockable(self):
        sim,pw,_,blocker=self.fixture()
        card=next(card for card in sim.players[0].library if card.kind=='creature')
        sim.players[0].library.remove(card)
        normal=s.Permanent(card)
        sim.players[0].battlefield.append(normal)
        self.assertTrue(sim.can_block(normal,blocker))
        sim.invariant()

    def test_countered_loyalty_does_not_create_ninja(self):
        sim,pw,source,_=self.fixture()
        ability=activate(sim,0,pw.id,1)
        self.assertIsNotNone(sim.counter_stack_item(ability))
        self.assertEqual(source.loyalty,1)
        self.assertEqual(len([x for x in sim.players[0].battlefield if x.card.is_token]),0)
        sim.invariant()

if __name__=='__main__':unittest.main()
