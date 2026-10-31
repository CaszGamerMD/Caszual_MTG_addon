"""Liliana-style Oracle blocks without pretending unsupported emblems are playable."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from planeswalker_runtime import activate,legal
from planeswalker_loyalty import compile_card,inspect_card

LILIANA_PAIR=(
    "+1: Up to one target creature gets -2/-1 until your next turn.\n"
    "−2: Mill two cards, then you may return a creature card from your graveyard to your hand.")
LILIANA_ULTIMATE=(
    "−7: You get an emblem with \"At the beginning of your end step, create X 2/2 "
    "black Zombie creature tokens, where X is two plus the number of Zombies you control.\"")

class ComposedLoyaltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def raw(self,text=LILIANA_PAIR,loyalty='3',name='Unknown Hopewalker'):
        return dict(name=name,layout='normal',types=['Planeswalker'],
                    superTypes=['Legendary'],subTypes=['Unknown'],
                    manaCost='{1}{B}{B}',oracleText=text,loyalty=loyalty,
                    colors=['Black'])

    def setup_game(self,creature_toughness=2):
        raw=self.raw()
        pw=s.import_diagnostic_card(self.rules,raw,0,'pw-unknown',{'Black'})
        self.assertEqual(pw.kind,'planeswalker')
        lands=[s.Card('pw-mana-'+str(i),'Mana','land',mask=63) for i in range(6)]
        opponent=s.Card('pw-opponent-creature','Two-power creature','creature',
                        power=2,toughness=creature_toughness,
                        traits='2;'+str(creature_toughness)+';',
                        event_definition=s.EventDefinition('Two-power creature',
                            frozenset({'Creature'}),frozenset(),False,2,
                            creature_toughness,frozenset()))
        sim=s.Simulator(self.rules,53,
            decks=(s.demo_deck(0)+[pw]+lands,s.demo_deck(1)+[opponent]),
            diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.phase='main';sim.manual_priority=True
        me,them=sim.players
        for c in [pw]+lands:
            (me.hand if c in me.hand else me.library).remove(c)
        (them.hand if opponent in them.hand else them.library).remove(opponent)
        me.hand.append(pw)
        me.battlefield.extend(s.Permanent(x) for x in lands)
        their_permanent=s.Permanent(opponent)
        them.battlefield.append(their_permanent)
        sim.cast_spell(0,pw)
        self.drain(sim)
        return sim,pw,their_permanent

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_whole_text_and_number_variants(self):
        program=compile_card(self.raw())
        self.assertEqual([ability.effect_kind for ability in program.abilities],
                         ['timed_modifier','mill_optional_creature_return'])
        self.assertEqual([ability.delta for ability in program.abilities],[1,-2])
        self.assertEqual(program.abilities[0].target_kind,'up_to_one_creature')
        altered=self.raw(text=LILIANA_PAIR.replace('-2/-1','-3/-2').replace(
            'Mill two cards','Mill three cards'),name='Unseen new planeswalker')
        self.assertEqual(compile_card(altered).abilities[0].program.power,-3)
        self.assertEqual(compile_card(altered).abilities[1].program.amount,3)
        self.assertIsNotNone(compile_card(self.raw(text=LILIANA_PAIR+'\n'+LILIANA_ULTIMATE)))
        for text in (LILIANA_PAIR.replace('a creature card','any card'),
                     LILIANA_PAIR.replace('until your next turn','until end of turn'),
                     LILIANA_PAIR+'\nAt end step, draw a card.'):
            with self.subTest(text=text):
                self.assertIsNone(compile_card(self.raw(text=text)))
        self.assertTrue(inspect_card(self.raw(text=LILIANA_PAIR+'\n'+LILIANA_ULTIMATE))['executionReady'])

    def test_target_binding_before_payment_and_no_target_is_allowed(self):
        sim,pw,target=self.setup_game()
        targets={(c.activation_index,c.target_permanent)
                 for c in legal(sim,0)}
        self.assertIn((0,''),targets)
        self.assertIn((0,target.card.id),targets)
        self.assertIn((1,''),targets)
        balance=next(x for x in sim.players[0].battlefield if x.card.id==pw.id).loyalty
        with self.assertRaises(ValueError):
            activate(sim,0,pw.id,0,'missing-creature')
        self.assertEqual(next(x for x in sim.players[0].battlefield if x.card.id==pw.id).loyalty,
                         balance)
        self.assertFalse(sim.stack.items)
        frame=activate(sim,0,pw.id,0,'')
        self.assertEqual(frame.payload[0]['target'],'')
        self.drain(sim)
        self.assertEqual(target.temporary_power,0)
        sim.invariant()

    def test_resolves_modifier_and_survives_opponents_cleanup(self):
        sim,pw,target=self.setup_game()
        activate(sim,0,pw.id,0,target.card.id)
        self.drain(sim)
        self.assertEqual((target.temporary_power,target.temporary_toughness),(-2,-1))
        self.assertFalse(sim.finished,(sim.result,sim.questions))
        self.assertEqual(sim.event_game('main').stats(sim.event_game('main').battlefield[target.card.id]),(0,1))
        sim.phase='cleanup'
        sim._step()
        self.assertEqual((target.temporary_power,target.temporary_toughness),(-2,-1))
        self.assertEqual(sim.phase,'end',(sim.phase,sim.result,sim.events[-5:]))
        self.assertFalse(sim.finished,(sim.result,sim.events[-7:]))
        sim._step() # opponent turn begins
        self.assertEqual(sim.active,1)
        sim.phase='cleanup';sim._step()
        self.assertEqual((target.temporary_power,target.temporary_toughness),(-2,-1))
        sim._step() # controller's next turn begins; effect expires
        self.assertEqual(sim.active,0)
        self.assertEqual((target.temporary_power,target.temporary_toughness),(0,0))
        sim.invariant()

    def test_toughness_zero_dies_and_reenter_does_not_inherit(self):
        sim,pw,target=self.setup_game(creature_toughness=1)
        activate(sim,0,pw.id,0,target.card.id)
        self.drain(sim)
        self.assertNotIn(target,sim.players[1].battlefield)
        self.assertIn(target.card,sim.players[1].graveyard)
        sim.invariant()

    def test_target_removed_while_on_stack_fizzles(self):
        sim,pw,target=self.setup_game()
        activate(sim,0,pw.id,0,target.card.id)
        sim.players[1].battlefield.remove(target)
        sim.players[1].graveyard.append(target.card)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='loyalty_target_fizzle' for e in sim.events))
        self.assertEqual(target.temporary_power,0)
        sim.invariant()

    def test_mill_two_then_may_return_milled_creature(self):
        sim,pw,_=self.setup_game()
        # Put two actual cards atop the local library and retain conservation.
        me=sim.players[0]
        creature=next(x for x in me.library if x.kind=='creature')
        land=next(x for x in me.library if x.kind=='land')
        for x in (creature,land):me.library.remove(x)
        me.library.extend([land,creature])
        before=len(me.library)
        activate(sim,0,pw.id,1)
        self.drain(sim)
        self.assertEqual(len(me.library),before-2)
        self.assertIn(creature,me.hand)
        self.assertNotIn(creature,me.graveyard)
        self.assertIn(land,me.graveyard)
        self.assertTrue(any(e['kind']=='loyalty_graveyard_return' for e in sim.events))
        sim.invariant()

    def test_countering_activation_prevents_both_mill_and_return(self):
        sim,pw,_=self.setup_game()
        before=len(sim.players[0].library)
        frame=activate(sim,0,pw.id,1)
        self.assertIsNotNone(sim.counter_stack_item(frame))
        self.assertEqual(len(sim.players[0].library),before)
        self.assertFalse(legal(sim,0))
        sim.invariant()

if __name__=='__main__':unittest.main()
