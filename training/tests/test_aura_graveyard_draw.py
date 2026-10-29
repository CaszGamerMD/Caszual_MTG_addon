"""Aura graveyard draw is an independent delayed trigger with complete Oracle parsing."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class AuraGraveyardDrawChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_unseen_name_full_program_and_unknown_clause(self):
        raw=dict(self.lookup['Audacity'],name='Unseen graveyard-draw Aura')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertEqual(parsed.kind,'aura')
        self.assertTrue(parsed.event_definition.aura_graveyard_draw)
        self.assertEqual(parsed.event_definition.attachment[3:5],(2,0))
        self.assertIn('trample',parsed.event_definition.attachment[2])
        raw['oracleText']+='\nIf you are lucky, take an extra turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        raw['oracleText']=raw['oracleText'].replace('draw a card.','draw two cards.').split('\nIf')[0]
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad2',{'Green'}).kind,'unsupported')

    def test_graveyard_move_queues_stack_draw_not_immediate(self):
        sim,cards=self.fixture(['Audacity'])
        host=self.token(sim,'host')
        aura=self.put(sim,cards['Audacity'],host.card.id)
        self.assertEqual(sim.effective_card(host).power,4)
        self.assertIn('trample',sim.effective_card(host).traits)
        before=len(sim.players[0].hand)
        sim.send_to_destination(sim.players[0],aura)
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertEqual(sim.effective_card(host).power,2)
        sim.resolve_entry_triggers([],aura.card)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_exile_does_not_draw_and_host_departure_does(self):
        sim,cards=self.fixture(['Audacity'])
        host=self.token(sim,'enemy-host',seat=1)
        aura=self.put(sim,cards['Audacity'],host.card.id)
        before=len(sim.players[0].hand)
        sim.send_to_destination(sim.players[0],aura,to_exile=True)
        sim.resolve_entry_triggers([],aura.card)
        self.assertFalse(sim.stack.items)
        self.assertEqual(len(sim.players[0].hand),before)
        sim.invariant()
        sim,cards=self.fixture(['Audacity'])
        host=self.token(sim,'host')
        aura=self.put(sim,cards['Audacity'],host.card.id)
        before=len(sim.players[0].hand)
        sim.send_to_destination(sim.players[0],host)
        sim.resolve_entry_triggers([],aura.card)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()
