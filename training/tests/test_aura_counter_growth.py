"""Hydra-style Aura entry counter and upkeep doubling event grammar."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class AuraCounterGrowthChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def upkeep(self,sim):
        sim.phase='untap'
        sim.stack.active=sim.active
        sim.stack.priority=sim.active
        sim.step()

    def test_actual_card_and_unseen_name_are_whole_text_supported(self):
        raw=dict(self.lookup["Hydra's Growth"],name="Unknown enchanted hydra")
        card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.entry_attachment_counters,1)
        self.assertTrue(card.event_definition.double_attachment_counters_upkeep)
        raw['oracleText']+='\nAt your upkeep, invent a random bonus.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',set()).kind,'unsupported')

    def test_counter_on_enter_uses_stack_then_doubles_on_upkeep(self):
        sim,cards=self.fixture(["Hydra's Growth"])
        creature=self.token(sim,'creature')
        self.put(sim,cards["Hydra's Growth"],creature.card.id)
        self.assertEqual(creature.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(creature.counters,1)
        self.upkeep(sim)
        self.assertEqual(creature.counters,1)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(creature.counters,2)
        sim.invariant()

    def test_hardened_scales_replaces_each_counter_event(self):
        sim,cards=self.fixture(["Hydra's Growth",'Hardened Scales'])
        self.put(sim,cards['Hardened Scales'])
        creature=self.token(sim,'creature')
        self.put(sim,cards["Hydra's Growth"],creature.card.id)
        self.drain(sim)
        self.assertEqual(creature.counters,2)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(creature.counters,5)
        sim.invariant()

    def test_branching_evolution_doubles_new_counters_not_existing_ones(self):
        sim,cards=self.fixture(["Hydra's Growth",'Branching Evolution'])
        self.put(sim,cards['Branching Evolution'])
        creature=self.token(sim,'creature')
        self.put(sim,cards["Hydra's Growth"],creature.card.id)
        self.drain(sim)
        self.assertEqual(creature.counters,2)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(creature.counters,6)
        sim.invariant()

    def test_aura_removed_after_entry_does_not_place_counter(self):
        sim,cards=self.fixture(["Hydra's Growth"])
        creature=self.token(sim,'creature')
        aura=self.put(sim,cards["Hydra's Growth"],creature.card.id)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertEqual(creature.counters,0)
        sim.invariant()

    def test_upkeep_count_read_on_resolution_and_not_on_trigger(self):
        sim,cards=self.fixture(["Hydra's Growth"])
        creature=self.token(sim,'creature')
        self.put(sim,cards["Hydra's Growth"],creature.card.id);self.drain(sim)
        self.upkeep(sim)
        creature.counters=3
        self.drain(sim)
        self.assertEqual(creature.counters,6)
        sim.invariant()

    def test_zero_counters_remain_zero_after_upkeep(self):
        sim,cards=self.fixture(["Hydra's Growth"])
        creature=self.token(sim,'creature')
        self.put(sim,cards["Hydra's Growth"],creature.card.id);self.drain(sim)
        creature.counters=0
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(creature.counters,0)
        sim.invariant()
