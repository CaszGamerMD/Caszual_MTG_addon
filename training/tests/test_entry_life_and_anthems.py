"""Shared entry lifegain and combined anthem regression checks."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from oracle_abilities import compile_abilities

class EntryLifeAnthemChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_actual_cards_and_renamed_text_fail_closed(self):
        for name in ("Ajani's Welcome",'Spidersilk Armor'):
            raw=dict(self.lookup[name]);raw['name']='Unfamiliar rules source'
            self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'x',set()).kind,'unsupported')
            raw['oracleText']+='\nDraw three extra cards.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities('Creatures you control get +0/+1 and have reach and imaginary.'))

    def test_entry_gain_waits_for_stack_and_survives_source(self):
        sim,cards=self.fixture(["Ajani's Welcome"])
        source=self.put(sim,cards["Ajani's Welcome"])
        self.assertFalse(sim.stack.items)
        for seat in (1,0,0):
            card=s.Card('arrival'+str(seat)+str(len(sim.players[seat].battlefield)),'Arrival','creature','{0}','2;2;',2,2,is_token=True)
            pending=sim.enter_creature(card,sim.players[seat])
            sim.resolve_entry_triggers(pending,card)
        self.assertEqual(len(sim.stack.items),2)
        self.assertEqual(sim.players[0].life,40)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[42,40])
        sim.invariant()

    def test_anthem_tracks_controller_and_source_leaving(self):
        sim,cards=self.fixture(['Spidersilk Armor'])
        own=self.token(sim,'own');enemy=self.token(sim,'enemy',1)
        source=self.put(sim,cards['Spidersilk Armor'])
        self.assertEqual(sim.effective_card(own).toughness,3)
        self.assertIn('reach',sim.effective_card(own).traits)
        self.assertEqual(sim.effective_card(enemy).toughness,2)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.effective_card(own).toughness,2)
        self.assertNotIn('reach',sim.effective_card(own).traits)
        sim.invariant()
