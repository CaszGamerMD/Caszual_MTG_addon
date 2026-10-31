"""Verified reusable targeting, temporary, and conditional spell blocks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from composed_modifier_blocks import parse
import simulator as s


STRENGTH = ('Target creature gets +2/+2 until end of turn. '
            'If you control an Equipment, create a 1/1 white Human Soldier creature token.')
WISPS = 'Target creature becomes black and gains fear until end of turn. Draw a card.'
MANEUVER = ('Up to two target creatures each get +1/+1 and gain lifelink '
            'until end of turn.')


class ComposedModifierBlockChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=s.RulesBridge()

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def card(self,text,name='Unknown spell',cost='{W}',types=('Instant',)):
        raw=dict(name=name,layout='normal',types=list(types),superTypes=[],subTypes=[],
                 manaCost=cost,oracleText=text,colors=['W'])
        return s.import_diagnostic_card(self.rules,raw,0,'composed-test',
                                        {'White','Black','Blue','Red','Green'})

    def fixture(self,spell,with_equipment=False):
        lands=[s.Card('composed-land-'+str(i),'Composed land','land',mask=63)
               for i in range(5)]
        allies=[s.Card('composed-ally-'+str(i),'Test creature','creature',
                       traits='2;3;',power=2,toughness=3,colors=('White',),
                       event_definition=s.EventDefinition('Test creature',
                           frozenset({'Creature'}),frozenset(),False,2,3,
                           frozenset(),colors=frozenset({'White'}))) for i in range(2)]
        opponent=s.Card('composed-enemy','Enemy creature','creature',power=3,toughness=2,
                        traits='3;2;',colors=('Red',),
                        event_definition=s.EventDefinition('Enemy creature',
                            frozenset({'Creature'}),frozenset(),False,3,2,
                            frozenset(),colors=frozenset({'Red'})))
        equipment=s.Card('composed-equipment','Equipment','mana_artifact',
                         event_definition=s.EventDefinition('Equipment',
                             frozenset({'Artifact'}),frozenset({'Equipment'}),
                             False,0,0,frozenset()))
        sim=s.Simulator(self.rules,42,
                        decks=(s.demo_deck(0)+[spell]+lands+allies+[equipment],
                               s.demo_deck(1)+[opponent]),diagnostic=True)
        sim.manual_priority=True
        sim.phase='main'
        p=sim.players[0]
        other=sim.players[1]
        for item in [spell]+lands+allies+[equipment]:
            (p.hand if item in p.hand else p.library).remove(item)
        (other.hand if opponent in other.hand else other.library).remove(opponent)
        p.hand.append(spell)
        p.battlefield.extend(s.Permanent(x) for x in lands+allies)
        if with_equipment:p.battlefield.append(s.Permanent(equipment))
        else:p.hand.append(equipment)
        other.battlefield.append(s.Permanent(opponent))
        return sim,allies,opponent,equipment

    @staticmethod
    def drain(sim):
        while sim.stack.items:
            sim.pass_priority(sim.stack.priority)

    @staticmethod
    def permanent(sim,card):
        return next(item for player in sim.players for item in player.battlefield
                    if item.card.id==card.id)

    @staticmethod
    def tokens(sim):
        return [item for item in sim.players[0].battlefield if item.card.is_token]

    def test_same_program_independent_of_card_name_and_numeric_words(self):
        spell=self.card(STRENGTH,name='Strength of Arms')
        self.assertEqual(spell.kind,'modifier_spell')
        self.assertEqual([step.operation for step in spell.modifier_program.steps],
                         ['modify_targets','create_tokens'])
        self.assertIsNotNone(self.card(STRENGTH,name='A made-up pump spell').modifier_program)
        unknown=self.card('Target creature gets +3/+2 and gains haste until end of turn.',
                          name='Unknown battle tactic')
        self.assertEqual((unknown.modifier_program.steps[0].modifier.power,
                          unknown.modifier_program.steps[0].modifier.toughness,
                          unknown.modifier_program.steps[0].modifier.keyword),(3,2,'haste'))
        self.assertEqual(self.card(STRENGTH+' Destroy target artifact.').kind,'unsupported')
        self.assertIsNone(parse('Target creature gains dancing until end of turn.',
                                ('Instant',)))
        self.assertIsNone(parse(STRENGTH,('Creature',)))

    def test_equipment_condition_evaluated_on_resolution_and_token_is_typed(self):
        spell=self.card(STRENGTH,name='Strength of Arms')
        sim,allies,_,equipment=self.fixture(spell)
        sim.cast_spell(0,spell,target=allies[0].id)
        self.assertEqual(self.permanent(sim,allies[0]).temporary_power,0)
        self.assertFalse(self.tokens(sim))
        # The condition is evaluated at resolution, after the spell is cast.
        p=sim.players[0]
        p.hand.remove(equipment)
        p.battlefield.append(s.Permanent(equipment))
        self.drain(sim)
        self.assertEqual((sim.effective_card(self.permanent(sim,allies[0])).power,
                          sim.effective_card(self.permanent(sim,allies[0])).toughness),(4,5))
        tokens=self.tokens(sim)
        self.assertEqual(len(tokens),1)
        self.assertEqual((tokens[0].card.power,tokens[0].card.toughness),(1,1))
        self.assertEqual(tokens[0].card.event_definition.colors,frozenset({'White'}))
        self.assertEqual(tokens[0].card.event_definition.subtypes,
                         frozenset({'Human','Soldier'}))
        sim.invariant()

    def test_condition_without_equipment_skips_token_not_buff(self):
        spell=self.card(STRENGTH)
        sim,allies,_,_=self.fixture(spell)
        sim.cast_spell(0,spell,target=allies[0].id)
        self.drain(sim)
        self.assertEqual(self.permanent(sim,allies[0]).temporary_power,2)
        self.assertEqual(self.tokens(sim),[])
        self.assertTrue(any(e['kind']=='modifier_condition_failed' for e in sim.events))
        sim.invariant()

    def test_illegal_target_fizzles_entire_spell_including_other_steps(self):
        spell=self.card(STRENGTH)
        sim,allies,_,_=self.fixture(spell,with_equipment=True)
        sim.cast_spell(0,spell,target=allies[0].id)
        victim=self.permanent(sim,allies[0])
        sim.players[0].battlefield.remove(victim)
        sim.players[0].graveyard.append(victim.card)
        self.drain(sim)
        self.assertEqual(self.tokens(sim),[])
        self.assertTrue(any(e['kind']=='modifier_fizzle' for e in sim.events))
        sim.invariant()

    def test_color_keyword_and_draw_expire_independently(self):
        spell=self.card(WISPS,name='Aphotic Wisps',cost='{B}')
        self.assertEqual(spell.kind,'modifier_spell')
        sim,allies,_,_=self.fixture(spell)
        owner=sim.players[0]
        library_before=len(owner.library)
        sim.cast_spell(0,spell,target=allies[0].id)
        self.assertEqual(len(owner.library),library_before)
        self.drain(sim)
        target=self.permanent(sim,allies[0])
        self.assertEqual(target.temporary_set_colors,frozenset({'Black'}))
        self.assertEqual(sim.effective_card(target).colors,('Black',))
        self.assertIn('fear',sim.effective_card(target).traits)
        self.assertEqual(len(owner.library),library_before-1)
        self.assertEqual(owner.graveyard.count(spell),1)
        sim.phase='cleanup'
        sim.step()
        self.assertEqual(target.temporary_set_colors,None)
        self.assertEqual(sim.effective_card(target).colors,('White',))
        self.assertNotIn('fear',sim.effective_card(target).traits)
        sim.invariant()

    def test_target_becomes_illegal_wisps_does_not_draw(self):
        spell=self.card(WISPS,cost='{B}')
        sim,allies,_,_=self.fixture(spell)
        library_before=len(sim.players[0].library)
        sim.cast_spell(0,spell,target=allies[0].id)
        victim=self.permanent(sim,allies[0])
        sim.players[0].battlefield.remove(victim)
        sim.players[0].graveyard.append(victim.card)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].library),library_before)
        sim.invariant()

    def test_up_to_two_targets_partial_legality_and_zero_selection(self):
        spell=self.card(MANEUVER,name='Cutthroat Maneuver')
        self.assertEqual(spell.kind,'modifier_spell')
        sim,allies,opponent,_=self.fixture(spell)
        sim.cast_spell(0,spell,target=(allies[0].id,opponent.id))
        victim=self.permanent(sim,allies[0])
        sim.players[0].battlefield.remove(victim)
        sim.players[0].graveyard.append(victim.card)
        self.drain(sim)
        survivor=self.permanent(sim,opponent)
        self.assertEqual((survivor.temporary_power,survivor.temporary_toughness),(1,1))
        self.assertIn('lifelink',sim.effective_card(survivor).traits)
        sim.invariant()
        zero=self.card(MANEUVER,name='Unknown no-target spell')
        empty,allies,_,_=self.fixture(zero)
        empty.cast_spell(0,zero,target=())
        self.drain(empty)
        self.assertEqual(self.permanent(empty,allies[0]).temporary_power,0)
        empty.invariant()

    def test_invalid_target_bindings_fail_before_mana_and_stack(self):
        spell=self.card(MANEUVER)
        sim,allies,_,_=self.fixture(spell)
        for bad in ((allies[0].id,allies[0].id),
                    (allies[0].id,allies[1].id,'nonexistent'),
                    ('nonexistent',),42):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    sim.cast_spell(0,spell,target=bad)
                self.assertIn(spell,sim.players[0].hand)
                self.assertFalse(sim.stack.items)
                self.assertTrue(all(not x.tapped for x in sim.players[0].battlefield
                                    if x.card.kind=='land'))
        sim.invariant()


if __name__=='__main__':
    unittest.main()
