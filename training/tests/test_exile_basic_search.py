"""Optional land search following targeted exile; always preserve hidden library zones."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures
import test_exile_creature_life as exile

class ExileBasicLandChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    drain=fixtures.EnchantmentChecks.drain
    creature=exile.ExileCreatureLifeChecks.creature

    def basic(self,sim,seat=1,identifier='search-basic',name='Plains'):
        mask={'Plains':1,'Island':2,'Swamp':4,'Mountain':8,'Forest':16}[name]
        card=s.Card(identifier,name,'land',mask=mask,land_subtypes=(name,),basic_land=True)
        sim.players[seat].library.append(card)
        sim.card_owners[card.id]=seat
        sim.total_cards=tuple(n+(i==seat) for i,n in enumerate(sim.total_cards))
        return card

    def test_real_path_and_unseen_named_text_compile_fail_closed(self):
        raw=dict(self.lookup['Path to Exile'],name='Unknown creature exile')
        card=s.import_diagnostic_card(self.rules,raw,0,'test',{'White'})
        self.assertEqual((card.kind,card.removal),('removal_spell','exile_creature_basic_land'))
        raw['oracleText']+='\nYour opponent invents two extra cards.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_opponent_finds_a_real_basic_tapped_then_shuffles(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'enemy',seat=1,power=4)
        basic=self.basic(sim,seat=1)
        initial=len(sim.players[1].library)
        sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
        self.assertIn(target,sim.players[1].battlefield)
        self.assertIn(basic,sim.players[1].library)
        self.drain(sim)
        self.assertIn(target.card,sim.players[1].exile)
        self.assertNotIn(target.card,sim.players[1].graveyard)
        self.assertNotIn(basic,sim.players[1].library)
        found=next(p for p in sim.players[1].battlefield if p.card.id==basic.id)
        self.assertTrue(found.tapped)
        self.assertEqual(len(sim.players[1].library),initial-1)
        self.assertEqual(sim.library_random_sequence,1)
        self.assertFalse(sim.land_played)
        sim.invariant()

    def test_owner_not_caster_gets_search_and_controller_not_owner_logic(self):
        sim,cards=self.fixture(['Path to Exile'])
        own=self.creature(sim,'own',seat=0)
        basic=self.basic(sim,seat=0,name='Forest')
        sim.cast_spell(0,cards['Path to Exile'],target=own.card.id)
        self.drain(sim)
        self.assertIn(own.card,sim.players[0].exile)
        self.assertTrue(any(p.card.id==basic.id and p.tapped for p in sim.players[0].battlefield))
        self.assertEqual(sim.players[1].life,40)
        sim.invariant()

    def test_optional_choice_declined_does_not_search_or_shuffle(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'enemy',seat=1)
        basic=self.basic(sim)
        initial=tuple(c.id for c in sim.players[1].library)
        with patch.object(sim,'choose_optional_basic_search',return_value=False):
            sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
            self.drain(sim)
        self.assertIn(target.card,sim.players[1].exile)
        self.assertEqual(tuple(c.id for c in sim.players[1].library),initial)
        self.assertEqual(sim.library_random_sequence,0)
        self.assertFalse(any(p.card.id==basic.id for p in sim.players[1].battlefield))
        sim.invariant()

    def test_search_may_find_nothing_and_still_shuffle(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'enemy',seat=1)
        with patch.object(sim,'choose_optional_basic_search',return_value=True):
            sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
            self.drain(sim)
        self.assertEqual(sim.library_random_sequence,1)
        self.assertFalse(any(p.card.basic_land for p in sim.players[1].battlefield))
        self.assertIn(target.card,sim.players[1].exile)
        sim.invariant()

    def test_no_available_basic_declines_under_default_policy(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'enemy',seat=1)
        sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target.card,sim.players[1].exile)
        self.assertEqual(sim.library_random_sequence,0)
        sim.invariant()

    def test_indestructible_exiled_and_basic_search_still_occurs(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'unbreakable',seat=1,abilities=('indestructible',))
        land=self.basic(sim)
        sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
        self.drain(sim)
        self.assertIn(target.card,sim.players[1].exile)
        self.assertTrue(any(p.card.id==land.id for p in sim.players[1].battlefield))
        sim.invariant()

    def test_fizzled_spell_does_not_offer_search_or_shuffle(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'vanishing',seat=1)
        land=self.basic(sim)
        sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
        sim.send_to_destination(sim.players[1],target)
        self.drain(sim)
        self.assertIn(target.card,sim.players[1].graveyard)
        self.assertIn(land,sim.players[1].library)
        self.assertEqual(sim.library_random_sequence,0)
        sim.invariant()

    def test_hexproof_opponent_cannot_be_targeted(self):
        sim,cards=self.fixture(['Path to Exile'])
        target=self.creature(sim,'safe',seat=1,abilities=('hexproof',))
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Path to Exile'],target=target.card.id)
        self.assertIn(cards['Path to Exile'],sim.players[0].hand)
        sim.invariant()
