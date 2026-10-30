"""Reusable self/opponent/all-player mill, whole-program gate and stack transitions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class MillLanguageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    drain=fixtures.EnchantmentChecks.drain

    def make_raw(self,text,name='Unknown Librarian'):
        raw=dict(self.lookup['Faerie Seer'])
        raw['name']=name
        raw['oracleText']='Flying\nWhen this creature enters, '+text
        return raw

    def test_new_names_numbers_and_targets_fail_closed(self):
        for instruction,seat,count in (
            ('you mill one card.','controller',1),
            ('each opponent mills 4 cards.','each opponent',4),
            ('each player mills three cards.','each player',3),
            ('each player mills 17 cards.','each player',17)):
            raw=self.make_raw(instruction)
            card=s.import_diagnostic_card(self.rules,raw,0,'mil',{'Blue'})
            self.assertNotEqual(card.kind,'unsupported',instruction)
            effect=card.event_definition.triggers[0].effect
            self.assertEqual((effect.operation,effect.recipient,effect.amount),
                             ('mill_cards',seat,count))
            raw['oracleText']+='\nDraw a card from nowhere.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Blue'}).kind,
                             'unsupported')
        for instruction in ('target player mills two cards.',
                            'each opponent mills X cards.',
                            'each player mills two cards, then draws one.'):
            self.assertEqual(s.import_diagnostic_card(self.rules,self.make_raw(instruction),
                                                       0,'bad',{'Blue'}).kind,'unsupported')
        # Eye Collector needs separate combat-damage trigger composition.
        self.assertEqual(s.import_diagnostic_card(self.rules,self.lookup['Eye Collector'],
                                                   0,'real',{'Blue','Black'}).kind,'unsupported')

    def test_each_player_mill_waits_on_stack_and_moves_correct_top_cards(self):
        card=s.import_diagnostic_card(self.rules,
              self.make_raw('each player mills two cards.'),0,'mill',{'Blue'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True
        p=sim.players[0];(p.hand if card in p.hand else p.library).remove(card)
        before=[list(owner.library) for owner in sim.players]
        grave=[list(owner.graveyard) for owner in sim.players]
        pending=sim.enter_creature(card,p)
        sim.resolve_entry_triggers(pending,card)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual([owner.library for owner in sim.players],before)
        self.drain(sim)
        for seat,owner in enumerate(sim.players):
            self.assertEqual(owner.library,before[seat][:-2])
            self.assertEqual(owner.graveyard,grave[seat]+before[seat][-1:-3:-1])
        event=sim.events[-1]
        self.assertEqual(event['details']['operation'],'mill_cards')
        self.assertEqual(event['details']['milledCounts'],{'0':2,'1':2})
        self.assertFalse(any(owner.failed_draw for owner in sim.players))
        sim.invariant()

    def test_each_opponent_mill_and_empty_library_are_legal(self):
        card=s.import_diagnostic_card(self.rules,
             self.make_raw('each opponent mills 6 cards.'),0,'mill',{'Blue'})
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
        own=list(sim.players[0].library)
        other=sim.players[1]
        other.graveyard.extend(other.library);other.library.clear()
        sim._resolve_entry_effects([dict(operation='mill_cards',recipient='each opponent',
                                         controller=0,source='trigger',amount=6)],card)
        self.assertEqual(sim.players[0].library,own)
        self.assertEqual(other.library,[])
        self.assertEqual(sim.events[-1]['details']['milledCounts'],{'1':0})
        self.assertFalse(other.failed_draw)
        sim.invariant()
