"""ETB self-sacrifice unless a different controlled creature returns to owner hand."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class EntryBounceChoiceChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    token=fixtures.EnchantmentChecks.token

    def test_real_renamed_and_unknown_text(self):
        raw=dict(self.lookup['Faerie Impostor'],name='Unknown Arrival Impostor')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'Blue'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertIn('flying',card.event_definition.abilities)
        self.assertEqual(card.event_definition.triggers[0].effect.operation,'self_sacrifice_unless_bounce')
        raw['oracleText']+='\nDraw one mystery card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Blue'}).kind,'unsupported')

    def test_return_other_card_to_owner_hand_without_targeting(self):
        sim,cards=self.fixture(['Faerie Impostor'])
        other=next(c for c in sim.players[0].library if c.kind=='creature')
        sim.players[0].library.remove(other)
        sim.enter_creature(other,sim.players[0])
        self.put(sim,cards['Faerie Impostor'])
        self.assertTrue(any(frame.payload[0]['operation']=='self_sacrifice_unless_bounce' for frame in sim.stack.items))
        self.drain(sim)
        self.assertIn(other,sim.players[0].hand)
        self.assertTrue(any(p.card.id==cards['Faerie Impostor'].id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_no_other_creature_sacrifices_source_after_stack(self):
        sim,cards=self.fixture(['Faerie Impostor'])
        source=self.put(sim,cards['Faerie Impostor'])
        self.assertIn(source,sim.players[0].battlefield)
        self.drain(sim)
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertIn(source.card,sim.players[0].graveyard)
        sim.invariant()

    def test_optional_decline_sacrifices_even_with_other_creature(self):
        sim,cards=self.fixture(['Faerie Impostor'])
        other=self.token(sim,'other')
        source=self.put(sim,cards['Faerie Impostor'])
        with patch.object(sim,'choose_optional_entry_bounce',return_value=None):self.drain(sim)
        self.assertIn(other,sim.players[0].battlefield)
        self.assertIn(source.card,sim.players[0].graveyard)
        sim.invariant()

    def test_token_return_ceases_to_exist_and_source_leaving_fizzles(self):
        sim,cards=self.fixture(['Faerie Impostor'])
        token=self.token(sim,'other')
        source=self.put(sim,cards['Faerie Impostor'])
        self.drain(sim)
        self.assertNotIn(token,sim.players[0].battlefield)
        self.assertFalse(any(c.id==token.card.id for c in sim.players[0].hand))
        sim.invariant()
        sim2,cards2=self.fixture(['Faerie Impostor'])
        source2=self.put(sim2,cards2['Faerie Impostor'])
        sim2.send_to_destination(sim2.players[0],source2,to_hand=True)
        self.drain(sim2)
        self.assertIn(source2.card,sim2.players[0].hand)
        self.assertFalse(any(e['kind']=='entry_sacrifice' for e in sim2.events))
        sim2.invariant()
