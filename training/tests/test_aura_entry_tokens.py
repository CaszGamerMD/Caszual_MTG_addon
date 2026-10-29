"""Aura enter-the-battlefield token triggers compose with attachment restrictions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class AuraEntryTokenChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_saved_cartouche_unseen_name_and_strict_unknown_clause(self):
        raw=dict(self.lookup['Cartouche of Solidarity'],name='Unseen cartouche')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'White'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.attachment[5],'controller')
        self.assertEqual(card.event_definition.triggers[0].effect.operation,'create_tokens')
        raw['oracleText']=raw['oracleText'].replace('1/1 white Warrior','2/2 green Elf')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'variant',{'Green'}).kind,'aura')
        raw['oracleText']+='\nIf the moon is full, draw an extra card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_existing_counter_entry_aura_still_parses(self):
        raw=self.lookup["Hydra's Growth"]
        card=s.import_diagnostic_card(self.rules,raw,0,'growth',{'Green'})
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.entry_attachment_counters,1)
        self.assertTrue(card.event_definition.double_attachment_counters_upkeep)

    def test_aura_enters_then_token_trigger_resolves_after_priority(self):
        sim,cards=self.fixture(['Cartouche of Solidarity'])
        host=self.token(sim,'host')
        aura=self.put(sim,cards['Cartouche of Solidarity'],host.card.id)
        self.assertEqual(aura.attached_to,host.card.id)
        self.assertEqual(sim.effective_card(host).power,3)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token and p.card.id!='host']),0)
        self.drain(sim)
        warriors=[p for p in sim.players[0].battlefield if p.card.is_token and
                  'Warrior' in p.card.event_definition.subtypes]
        self.assertEqual(len(warriors),1)
        self.assertIn('vigilance',sim.effective_card(warriors[0]).traits)
        sim.invariant()

    def test_trigger_survives_aura_leaving_and_token_replacement(self):
        sim,cards=self.fixture(['Cartouche of Solidarity','Parallel Lives'])
        host=self.token(sim,'host')
        self.put(sim,cards['Parallel Lives'])
        aura=self.put(sim,cards['Cartouche of Solidarity'],host.card.id)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        warriors=[p for p in sim.players[0].battlefield if p.card.is_token and
                  'Warrior' in p.card.event_definition.subtypes]
        self.assertEqual(len(warriors),2)
        sim.invariant()
