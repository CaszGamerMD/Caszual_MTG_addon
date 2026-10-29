"""Artifact entry choices share the dynamic chosen-type anthem engine."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as h
class ArtifactChoiceTests(unittest.TestCase):
    setUpClass=classmethod(h.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(h.EnchantmentChecks.tearDownClass.__func__)
    fixture=h.EnchantmentChecks.fixture
    put=h.EnchantmentChecks.put
    token=h.EnchantmentChecks.token
    drain=h.EnchantmentChecks.drain
    def test_full_oracle_unseen_and_extra_clause(self):
        raw=dict(self.lookup['Instruments of War'],name='Unseen type banner')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',set())
        self.assertEqual(card.kind,'artifact')
        self.assertTrue(card.event_definition.chosen_type_entry)
        self.assertIn('flash',card.event_definition.abilities)
        raw['oracleText']=raw['oracleText'].replace('+1/+1','+2/+0')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'other',set()).kind,'artifact')
        raw['oracleText']+='\nUnrecognized ability.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
    def test_flash_artifact_cast_during_opponent_turn(self):
        sim,cards=self.fixture(['Instruments of War'])
        card=cards['Instruments of War']
        self.assertTrue(card.instant)
        sim.active=1
        sim.phase='main'
        sim.stack.priority=0
        self.assertIn(card,sim.response_choices(0))
        sim.cast_spell(0,card)
        self.assertEqual(sim.stack.items[-1].payload[1].id,card.id)
        self.drain(sim)
        self.assertTrue(any(p.card.id==card.id for p in sim.players[0].battlefield))
        sim.invariant()
    def test_live_chosen_type_scope_and_departure(self):
        sim,cards=self.fixture(['Instruments of War'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        self.token(sim,'goblin-two',subtypes=('Goblin',))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        banner=self.put(sim,cards['Instruments of War'])
        self.assertEqual(banner.chosen_subtype,'Goblin')
        self.assertEqual(sim.effective_card(goblin).power,3)
        self.assertEqual(sim.effective_card(elf).power,2)
        self.assertEqual(sim.effective_card(enemy).power,2)
        sim.send_to_destination(sim.players[0],banner)
        self.assertEqual(sim.effective_card(goblin).power,2)
        sim.invariant()
