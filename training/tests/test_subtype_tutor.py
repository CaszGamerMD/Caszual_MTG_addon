"""Subtype-constrained library tutor: optional, hidden search, reveal, shuffle."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class SubtypeTutorChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def candidate(self,sim,identifier,subtype='Goblin',seat=0,kind='creature'):
        card=s.Card(identifier,'Unknown '+identifier,kind,printed_types=('Creature',),
                    land_subtypes=(subtype,),power=2,toughness=2,traits='2;2;')
        p=sim.players[seat]
        p.library.insert(0,card)
        sim.card_owners[card.id]=seat
        sim.total_cards=tuple(n+(i==seat) for i,n in enumerate(sim.total_cards))
        return card

    def test_matron_and_unseen_name_parse_without_card_specific_dispatch(self):
        raw=dict(self.lookup['Goblin Matron'],name='Unfamiliar tribal librarian')
        card=s.import_diagnostic_card(self.rules,raw,0,'matron',{'Red'})
        self.assertEqual(card.kind,'creature')
        trigger=card.event_definition.triggers[0]
        self.assertEqual(trigger.event,'enters')
        self.assertEqual(trigger.effect.operation,'optional_subtype_search_hand')
        self.assertEqual(trigger.effect.library_filter,('subtype','Goblin'))
        raw['oracleText']+='\nSearch for an impossible card at midnight.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')

    def test_successful_tutor_waits_for_stack_and_reveals_selected_card(self):
        sim,cards=self.fixture(['Goblin Matron'])
        found=self.candidate(sim,'first-goblin')
        nonmatching=self.candidate(sim,'first-merfolk',subtype='Merfolk')
        before=len(sim.players[0].hand)
        self.put(sim,cards['Goblin Matron'])
        self.assertEqual(len(sim.stack.items),1)
        self.assertIn(found,sim.players[0].library)
        self.drain(sim)
        self.assertIn(found,sim.players[0].hand)
        self.assertNotIn(found,sim.players[0].library)
        self.assertIn(nonmatching,sim.players[0].library)
        # Casting/putting Matron onto the field removes it from hand,
        # and the successful tutor replaces it with one chosen card.
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertEqual(sim.library_random_sequence,1)
        self.assertTrue(any(e['kind']=='search_reveal' and
                            e['details'].get('revealed')==found.name for e in sim.events))
        sim.invariant()

    def test_optional_search_may_be_declined_and_does_not_shuffle(self):
        sim,cards=self.fixture(['Goblin Matron'])
        found=self.candidate(sim,'choice')
        original=tuple(c.id for c in sim.players[0].library)
        self.put(sim,cards['Goblin Matron'])
        with patch.object(sim,'choose_optional_subtype_search',return_value=False):
            self.drain(sim)
        self.assertEqual(original,tuple(c.id for c in sim.players[0].library))
        self.assertNotIn(found,sim.players[0].hand)
        self.assertEqual(sim.library_random_sequence,0)
        sim.invariant()

    def test_accepted_hidden_search_can_fail_to_find_and_still_shuffles(self):
        sim,cards=self.fixture(['Goblin Matron'])
        self.put(sim,cards['Goblin Matron'])
        with patch.object(sim,'choose_optional_subtype_search',return_value=True):
            self.drain(sim)
        self.assertEqual(sim.library_random_sequence,1)
        self.assertTrue(any(e['kind']=='search_reveal' and
                            e['details'].get('revealed') is None for e in sim.events))
        sim.invariant()

    def test_tutor_finds_matching_subtype_and_not_generic_creature(self):
        sim,cards=self.fixture(['Goblin Matron'])
        other=self.candidate(sim,'other-type',subtype='Wizard')
        found=self.candidate(sim,'both',subtype='Goblin')
        self.put(sim,cards['Goblin Matron']);self.drain(sim)
        self.assertIn(found,sim.players[0].hand)
        self.assertIn(other,sim.players[0].library)
        sim.invariant()

    def test_search_still_resolves_when_matron_has_left_battlefield(self):
        sim,cards=self.fixture(['Goblin Matron'])
        goblin=self.candidate(sim,'goblin-after-death')
        matron=self.put(sim,cards['Goblin Matron'])
        sim.send_to_destination(sim.players[0],matron)
        self.drain(sim)
        self.assertIn(goblin,sim.players[0].hand)
        sim.invariant()

    def test_different_subtype_word_compiles_and_filters_by_it(self):
        raw=dict(self.lookup['Goblin Matron'],name='Unfamiliar elf librarian')
        raw['oracleText']=raw['oracleText'].replace('Goblin card','Elf card')
        sim,cards=self.fixture(['Goblin Matron'])
        elf=s.import_diagnostic_card(self.rules,raw,0,'elf-matron',{'Green'})
        self.assertEqual(elf.event_definition.triggers[0].effect.library_filter,('subtype','Elf'))
        target=self.candidate(sim,'elf-to-hand',subtype='Elf')
        self.candidate(sim,'goblin-not-eligible',subtype='Goblin')
        sim.players[0].library.append(elf)
        sim.card_owners[elf.id]=0
        sim.total_cards=tuple(n+(i==0) for i,n in enumerate(sim.total_cards))
        sim.players[0].library.remove(elf)
        pending=sim.enter_creature(elf,sim.players[0])
        sim.resolve_entry_triggers(pending,elf)
        self.drain(sim)
        self.assertIn(target,sim.players[0].hand)
        sim.invariant()
