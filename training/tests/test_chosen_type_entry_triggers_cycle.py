"""Chosen creature type ETB trigger: entry choice, scope, stack and counters."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class ChosenTypeEntryTriggerCycle(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_type_amount_and_reject_incomplete_program(self):
        raw=self.lookup['Bloodline Pretender']
        card=s.import_diagnostic_card(self.rules,raw,0,'real',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertTrue(card.event_definition.chosen_type_entry)
        self.assertTrue(card.event_definition.triggers[0].subject.chosen_subtype)
        other=dict(raw,name='Unseen Alltype Watcher',
            oracleText=raw['oracleText'].replace('a +1/+1 counter','two +1/+1 counters'))
        parsed=s.import_diagnostic_card(self.rules,other,0,'new',{'Green'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(parsed.event_definition.triggers[0].effect.amount,2)
        for text in (raw['oracleText'].replace('As this creature enters, choose a creature type.\n',''),
                     raw['oracleText']+'\nYou win the game.'):
            other['oracleText']=text
            self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad',{'Green'}).kind,'unsupported')

    def test_chosen_elf_only_other_controlled_entry_stacks_and_resolves(self):
        sim,cards=self.fixture(['Bloodline Pretender','Universal Automaton'])
        with patch.object(sim,'choose_creature_type',return_value='Elf'):
            watcher=self.put(sim,cards['Bloodline Pretender'])
        self.assertEqual(watcher.chosen_subtype,'Elf')
        self.assertEqual(watcher.counters,0)
        self.assertFalse(sim.stack.items)
        self.token(sim,'enemy-elf',seat=1,subtypes=('Elf',))
        self.assertFalse(sim.stack.items)
        self.token(sim,'own-goblin',seat=0,subtypes=('Goblin',))
        self.assertFalse(sim.stack.items)
        self.token(sim,'own-elf',seat=0,subtypes=('Elf',))
        definition=s.EventDefinition('Elf Scout',frozenset({'Creature'}),frozenset({'Elf'}),False,1,1,frozenset())
        entrant=s.Card('new-elf','Elf Scout','creature',event_definition=definition,is_token=True)
        pending=sim.enter_creature(entrant,sim.players[0]);sim.resolve_entry_triggers(pending,entrant)
        self.assertEqual(watcher.counters,0)
        self.assertTrue(sim.stack.items)
        self.drain(sim)
        self.assertEqual(watcher.counters,1)
        changeling=cards['Universal Automaton']
        self.put(sim,changeling)
        self.drain(sim)
        self.assertEqual(watcher.counters,2)
        sim.invariant()

    def test_chosen_type_does_not_trigger_for_opponent_and_source_can_leave(self):
        sim,cards=self.fixture(['Bloodline Pretender'])
        with patch.object(sim,'choose_creature_type',return_value='Squirrel'):
            source=self.put(sim,cards['Bloodline Pretender'])
        definition=s.EventDefinition('Squirrel',frozenset({'Creature'}),frozenset({'Squirrel'}),False,1,1,frozenset())
        for seat in (1,0):
            entrant=s.Card('sq-'+str(seat),'Squirrel','creature',event_definition=definition,is_token=True)
            pending=sim.enter_creature(entrant,sim.players[seat]);sim.resolve_entry_triggers(pending,entrant)
            if seat==1:self.assertFalse(sim.stack.items)
            else:self.assertTrue(sim.stack.items)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertNotIn(source,sim.players[0].battlefield)
        sim.invariant()

if __name__=='__main__':unittest.main()
