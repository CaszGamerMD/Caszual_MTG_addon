"""Intervening-if enchanted token trigger checks at both trigger and resolution."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class EnchantedUpkeepTokenCycle(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain

    def upkeep(self,sim):
        sim.phase='untap';sim.stack.active=sim.active;sim.stack.priority=sim.active;sim.step()

    def test_real_unseen_name_changed_amount_and_negative_remainder(self):
        raw=dict(self.lookup['Dreampod Druid'],name='Unknown garden keeper')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.upkeep_token_rule[0],'each')
        raw['oracleText']=raw['oracleText'].replace('a 1/1','two 1/1')
        card=s.import_diagnostic_card(self.rules,raw,0,'more',{'Green'})
        self.assertEqual(card.event_definition.upkeep_token_rule[-1].amount,2)
        raw['oracleText']+='\nDestroy all lands.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_no_trigger_when_unenchanted_and_trigger_on_opponent_upkeep(self):
        sim,cards=self.fixture(['Dreampod Druid','Hyena Umbra'])
        druid=self.put(sim,cards['Dreampod Druid'])
        self.upkeep(sim)
        self.assertFalse(sim.stack.items)
        aura=self.put(sim,cards['Hyena Umbra'],druid.card.id)
        sim.active=1
        self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sum(p.card.name=='Saproling' for p in sim.players[0].battlefield),1)
        sim.invariant()

    def test_intervening_if_rechecks_at_resolution_and_token_doubling(self):
        sim,cards=self.fixture(['Dreampod Druid','Hyena Umbra','Parallel Lives'])
        druid=self.put(sim,cards['Dreampod Druid'])
        aura=self.put(sim,cards['Hyena Umbra'],druid.card.id)
        self.put(sim,cards['Parallel Lives'])
        self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertFalse(any(p.card.name=='Saproling' for p in sim.players[0].battlefield))
        sim.invariant()

    def test_doubled_creation_when_still_enchanted(self):
        sim,cards=self.fixture(['Dreampod Druid','Hyena Umbra','Parallel Lives'])
        druid=self.put(sim,cards['Dreampod Druid'])
        self.put(sim,cards['Hyena Umbra'],druid.card.id)
        self.put(sim,cards['Parallel Lives'])
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(sum(p.card.name=='Saproling' for p in sim.players[0].battlefield),2)
        sim.invariant()
