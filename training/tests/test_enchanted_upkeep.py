"""Aura upkeep counter trigger uses current attachment and replacement effects."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class EnchantedUpkeepChecks(unittest.TestCase):
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

    def test_real_forced_adaptation_and_unknown_name_but_no_extra_text(self):
        raw=dict(self.lookup['Forced Adaptation'],name='Unknown attachment growth')
        card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.upkeep_attachment_counters,1)
        raw['oracleText']+='\nEnchant a random flying mouse.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_trigger_waits_on_stack_then_grants_counter(self):
        sim,cards=self.fixture(['Forced Adaptation'])
        target=self.token(sim,'target')
        self.put(sim,cards['Forced Adaptation'],target.card.id)
        self.upkeep(sim)
        self.assertEqual(target.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(target.counters,1)
        sim.invariant()

    def test_hardened_scales_and_branching_evolution_apply(self):
        sim,cards=self.fixture(['Forced Adaptation','Hardened Scales','Branching Evolution'])
        target=self.token(sim,'target')
        self.put(sim,cards['Hardened Scales'])
        self.put(sim,cards['Branching Evolution'])
        self.put(sim,cards['Forced Adaptation'],target.card.id)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(target.counters,4)
        sim.invariant()

    def test_removed_aura_cannot_resolve_on_former_host(self):
        sim,cards=self.fixture(['Forced Adaptation'])
        target=self.token(sim,'target')
        aura=self.put(sim,cards['Forced Adaptation'],target.card.id)
        self.upkeep(sim)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertEqual(target.counters,0)
        sim.invariant()

    def test_retargeted_aura_uses_current_enchanted_creature(self):
        sim,cards=self.fixture(['Forced Adaptation'])
        first=self.token(sim,'first')
        second=self.token(sim,'second')
        aura=self.put(sim,cards['Forced Adaptation'],first.card.id)
        self.upkeep(sim)
        aura.attached_to=second.card.id
        self.drain(sim)
        self.assertEqual((first.counters,second.counters),(0,1))
        sim.invariant()

    def test_unknown_numeric_count_is_parsed_from_text(self):
        raw=dict(self.lookup['Forced Adaptation'],name='Unseen increasing aura')
        raw['oracleText']=raw['oracleText'].replace('put a +1/+1 counter','put two +1/+1 counters')
        card=s.import_diagnostic_card(self.rules,raw,0,'x',{'Green'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.upkeep_attachment_counters,2)
