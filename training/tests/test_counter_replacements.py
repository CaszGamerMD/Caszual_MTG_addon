"""Generic +1/+1 replacement rules, independent of enchantment card names."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class CounterReplacementChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_both_actual_cards_and_unfamiliar_names_compile_fail_closed(self):
        for name in ('Hardened Scales','Branching Evolution'):
            raw=dict(self.lookup[name],name='Unknown counter replacement')
            card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
            self.assertNotEqual(card.kind,'unsupported',name)
            self.assertEqual(len(card.event_definition.counter_replacements),1)
            raw['oracleText']+='\nMystery counters do something impossible.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'If one or more +1/+1 counters would be put on a creature you control, '
            'three times that many mystery tokens are created instead.'))

    def test_hardened_scales_adds_one_to_each_positive_event(self):
        sim,cards=self.fixture(['Hardened Scales'])
        self.put(sim,cards['Hardened Scales'])
        creature=self.token(sim,'recipient')
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(creature.card.id,1),2)
        self.assertEqual(game.counter_amount(creature.card.id,2),3)
        self.assertEqual(game.counter_amount(creature.card.id,0),0)
        self.assertEqual(creature.counters,0)
        sim.invariant()

    def test_branching_evolution_doubles_and_stacks_with_hardened_scales(self):
        sim,cards=self.fixture(['Hardened Scales','Branching Evolution'])
        source=self.put(sim,cards['Hardened Scales'])
        self.put(sim,cards['Branching Evolution'])
        creature=self.token(sim,'recipient')
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(creature.card.id,1),4)
        self.assertEqual(game.counter_amount(creature.card.id,2),6)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.event_game('main').counter_amount(creature.card.id,1),2)
        sim.invariant()

    def test_counter_replacement_is_own_controller_only(self):
        sim,cards=self.fixture(['Hardened Scales'])
        self.put(sim,cards['Hardened Scales'])
        friendly=self.token(sim,'friendly')
        opponent=self.token(sim,'opponent',seat=1)
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(friendly.card.id,2),3)
        self.assertEqual(game.counter_amount(opponent.card.id,2),2)
        sim.invariant()

    def test_self_counter_trigger_applies_replacement_before_state_change(self):
        sim,cards=self.fixture(['Hardened Scales','Branching Evolution'])
        self.put(sim,cards['Hardened Scales'])
        self.put(sim,cards['Branching Evolution'])
        creature=self.token(sim,'recipient')
        sim._resolve_entry_effects([dict(operation='self_counter',effect='add counter',
             source=creature.card.id,name='Unknown source',controller=0,amount=2)],creature.card)
        self.assertEqual(creature.counters,6)
        self.assertEqual(sim.effective_card(creature).power,8)
        sim.invariant()

    def test_each_creature_gets_replacement_for_mass_counter_event(self):
        sim,cards=self.fixture(['Hardened Scales'])
        self.put(sim,cards['Hardened Scales'])
        a=self.token(sim,'a');b=self.token(sim,'b')
        enemy=self.token(sim,'enemy',seat=1)
        sim._resolve_entry_effects([dict(operation='add_counters',effect='counters',
             source='something',name='Unseen global counter ability',controller=0,amount=1)],a.card)
        self.assertEqual((a.counters,b.counters,enemy.counters),(2,2,0))
        sim.invariant()

    def test_counter_replacement_does_not_affect_non_creature(self):
        sim,cards=self.fixture(['Hardened Scales'])
        source=self.put(sim,cards['Hardened Scales'])
        game=sim.event_game('main')
        self.assertFalse(game.creature(game.battlefield[source.card.id]))
        self.assertEqual(game.counter_amount(source.card.id,2),2)
        sim.invariant()
