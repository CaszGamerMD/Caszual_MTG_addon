"""Reusable opponent-optional library search ETB rules."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures
import test_exile_basic_search as searching

class OpponentBasicEntryChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    basic=searching.ExileBasicLandChecks.basic

    def test_unfamiliar_name_compiles_whole_text_but_extra_ability_fails_closed(self):
        raw=dict(self.lookup['Old-Growth Dryads'],name='Unknown dryad-like creature')
        card=s.import_diagnostic_card(self.rules,raw,0,'dryad',{'Green'})
        self.assertEqual(card.kind,'creature')
        trigger=card.event_definition.triggers[0]
        self.assertEqual((trigger.event,trigger.effect.operation),
                         ('enters','opponent_optional_basic_search'))
        raw['oracleText']+='\nSearch the secret library for impossible cards.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_creature_enters_then_opponent_searches_on_stack_resolution(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        basic=self.basic(sim,seat=1,identifier='basic-1',name='Forest')
        before=len(sim.players[1].library)
        self.put(sim,cards['Old-Growth Dryads'])
        self.assertEqual(len(sim.stack.items),1)
        self.assertIn(basic,sim.players[1].library)
        self.drain(sim)
        self.assertNotIn(basic,sim.players[1].library)
        self.assertEqual(len(sim.players[1].library),before-1)
        self.assertTrue(any(p.card.id==basic.id and p.tapped for p in sim.players[1].battlefield))
        self.assertFalse(sim.land_played)
        self.assertEqual(sim.library_random_sequence,1)
        sim.invariant()

    def test_controller_does_not_search_own_library(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        self.basic(sim,seat=0,identifier='mine',name='Plains')
        self.put(sim,cards['Old-Growth Dryads']);self.drain(sim)
        self.assertTrue(any(c.id=='mine' for c in sim.players[0].library))
        self.assertFalse(any(p.card.id=='mine' for p in sim.players[0].battlefield))
        sim.invariant()

    def test_player_can_decline_and_library_remains_unchanged(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        basic=self.basic(sim,seat=1)
        before=tuple(c.id for c in sim.players[1].library)
        self.put(sim,cards['Old-Growth Dryads'])
        with patch.object(sim,'choose_optional_basic_search',return_value=False):
            self.drain(sim)
        self.assertEqual(tuple(c.id for c in sim.players[1].library),before)
        self.assertEqual(sim.library_random_sequence,0)
        self.assertFalse(any(p.card.id==basic.id for p in sim.players[1].battlefield))
        sim.invariant()

    def test_accepted_search_without_matching_basic_still_shuffles(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        self.put(sim,cards['Old-Growth Dryads'])
        with patch.object(sim,'choose_optional_basic_search',return_value=True):
            self.drain(sim)
        self.assertEqual(sim.library_random_sequence,1)
        sim.invariant()

    def test_trigger_survives_source_leaving_before_resolution(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        basic=self.basic(sim,seat=1)
        dryad=self.put(sim,cards['Old-Growth Dryads'])
        sim.send_to_destination(sim.players[0],dryad)
        self.drain(sim)
        self.assertTrue(any(p.card.id==basic.id and p.tapped for p in sim.players[1].battlefield))
        sim.invariant()

    def test_two_independent_entry_triggers_search_twice(self):
        sim,cards=self.fixture(['Old-Growth Dryads'])
        first=self.basic(sim,seat=1,identifier='first',name='Plains')
        second=self.basic(sim,seat=1,identifier='second',name='Forest')
        raw=dict(self.lookup['Old-Growth Dryads'],name='Another unknown dryad')
        other=s.import_diagnostic_card(self.rules,raw,0,'other-dryad',{'Green'})
        sim.players[0].library.append(other)
        sim.card_owners[other.id]=0
        sim.total_cards=tuple(n+(i==0) for i,n in enumerate(sim.total_cards))
        self.put(sim,cards['Old-Growth Dryads'])
        sim.players[0].library.remove(other)
        pending=sim.enter_creature(other,sim.players[0])
        sim.resolve_entry_triggers(pending,other)
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertTrue(all(any(p.card.id==basic.id and p.tapped
                                for p in sim.players[1].battlefield)
                            for basic in (first,second)))
        self.assertEqual(sim.library_random_sequence,2)
        sim.invariant()
