"""Strict surveil instruction grammar and ordered private zone decisions."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class SurveilLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    drain=fixtures.EnchantmentChecks.drain

    def make_card(self,amount=1,name='Unseen Dream-Messenger'):
        raw=dict(self.lookup['Faerie Dreamthief'])
        raw['name']=name
        raw['oracleText']=f'Flying\nWhen this creature enters, surveil {amount}.'
        return raw

    def test_whole_oracle_program_and_unknown_text_remain_fail_closed(self):
        for n in (1,2,5):
            raw=self.make_card(n,'Unseen Messenger '+str(n))
            card=s.import_diagnostic_card(self.rules,raw,0,str(n),{'Blue','Black'})
            self.assertNotEqual(card.kind,'unsupported')
            self.assertEqual(card.event_definition.triggers[0].effect.amount,n)
            self.assertEqual(card.event_definition.triggers[0].effect.operation,'surveil')
            raw['oracleText']+='\nWhenever you draw a mysterious card, win.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Blue','Black'}).kind,'unsupported')
        self.assertEqual(s.import_diagnostic_card(self.rules,self.lookup['Faerie Dreamthief'],
                                                   0,'real',{'Blue','Black'}).kind,'unsupported')

    def test_entry_trigger_waits_for_resolution_and_leaves_library_unchanged(self):
        card=s.import_diagnostic_card(self.rules,self.make_card(3),0,'seer',{'Blue','Black'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        p=sim.players[0]
        (p.hand if card in p.hand else p.library).remove(card)
        before=list(p.library)
        pending=sim.enter_creature(card,p)
        sim.resolve_entry_triggers(pending,card)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(p.library,before)
        self.drain(sim)
        self.assertEqual(p.library,before)
        events=[e for e in sim.events if e['details'].get('operation')=='surveil']
        self.assertEqual(len(events),1)
        self.assertIn('surveils 3',events[0]['message'])
        self.assertTrue(all(c.id not in events[0]['message'] for c in before[-3:]))
        sim.invariant()

    def test_distinct_card_choices_move_selected_to_graveyard_without_public_identity(self):
        card=s.import_diagnostic_card(self.rules,self.make_card(4),0,'seer',{'Blue','Black'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        before=list(p.library)
        looked=before[-4:]
        oldgrave=list(p.graveyard)
        visits=[]
        def choose(seat,c):
            self.assertEqual(seat,0)
            visits.append(c.id)
            return c in (looked[0],looked[2])
        with patch.object(sim,'choose_surveil_graveyard',side_effect=choose):
            sim._resolve_entry_effects([dict(operation='surveil',controller=0,source='trigger',amount=4)],card)
        self.assertEqual(visits,[c.id for c in looked])
        self.assertEqual(p.library,before[:-4]+[looked[1],looked[3]])
        self.assertEqual(p.graveyard,oldgrave+[looked[0],looked[2]])
        event=sim.events[-1]
        self.assertEqual(event['details']['movedToGraveyard'],2)
        self.assertEqual(event['details']['amount'],4)
        public=str(event['details'])+event['message']
        self.assertTrue(all(c.id not in public and c.name not in public for c in looked))
        sim.invariant()

    def test_empty_library_is_zero_surveil_not_a_failed_draw(self):
        card=s.import_diagnostic_card(self.rules,self.make_card(2),0,'seer',{'Blue','Black'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        p=sim.players[0]
        p.graveyard.extend(p.library);p.library.clear()
        sim._resolve_entry_effects([dict(operation='surveil',controller=0,source='trigger',amount=2)],card)
        self.assertEqual(sim.events[-1]['details']['amount'],0)
        self.assertIn('surveils 0',sim.events[-1]['message'])
        self.assertFalse(p.failed_draw)
        sim.invariant()
