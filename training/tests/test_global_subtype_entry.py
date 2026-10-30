"""Another creature subtype enters, independent of which player controls it."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class GlobalSubtypeEntryChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_and_reject_unknown_extra(self):
        raw=self.lookup['Elvish Vanguard']
        card=s.import_diagnostic_card(self.rules,raw,0,'vanguard',{'Green'})
        self.assertEqual(card.kind,'creature')
        trigger=card.event_definition.triggers[0]
        self.assertEqual(trigger.subject.subtype,'Elf')
        self.assertEqual(trigger.subject.relation,'any')
        self.assertTrue(trigger.subject.other)
        other=dict(raw,name='Unseen Goblin Vanguard',oracleText=raw['oracleText'].replace('Elf','Goblin'),subTypes=['Goblin','Warrior'])
        parsed=s.import_diagnostic_card(self.rules,other,0,'goblin',{'Green'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(parsed.event_definition.triggers[0].subject.subtype,'Goblin')
        other['oracleText']+='\nWhenever you sneeze, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad',{'Green'}).kind,'unsupported')

    def test_opponent_and_controller_entry_trigger_but_self_entry_does_not(self):
        sim,cards=self.fixture(['Elvish Vanguard'])
        source=self.put(sim,cards['Elvish Vanguard'])
        self.assertEqual(source.counters,0)
        self.assertEqual(len(sim.stack.items),0)
        elf=s.EventDefinition('Elf Ally',frozenset({'Creature'}),frozenset({'Elf'}),False,1,1,frozenset())
        other=s.Card('enemy','Enemy Elf','creature',event_definition=elf,is_token=True)
        pending=sim.enter_creature(other,sim.players[1]);sim.resolve_entry_triggers(pending,other)
        self.assertEqual(source.counters,0)
        self.assertGreater(len(sim.stack.items),0)
        self.drain(sim)
        self.assertEqual(source.counters,1)
        friend=s.Card('friend','Friendly Elf','creature',event_definition=elf,is_token=True)
        pending=sim.enter_creature(friend,sim.players[0]);sim.resolve_entry_triggers(pending,friend)
        self.drain(sim)
        self.assertEqual(source.counters,2)
        sim.invariant()

    def test_nonmatching_entry_and_source_removed_before_resolution(self):
        sim,cards=self.fixture(['Elvish Vanguard'])
        source=self.put(sim,cards['Elvish Vanguard'])
        gob=s.EventDefinition('Goblin',frozenset({'Creature'}),frozenset({'Goblin'}),False,1,1,frozenset())
        card=s.Card('gob','Goblin','creature',event_definition=gob,is_token=True)
        pending=sim.enter_creature(card,sim.players[1]);sim.resolve_entry_triggers(pending,card)
        self.assertFalse(sim.stack.items)
        elf=s.EventDefinition('Elf',frozenset({'Creature'}),frozenset({'Elf'}),False,1,1,frozenset())
        ally=s.Card('elf','Elf','creature',event_definition=elf,is_token=True)
        pending=sim.enter_creature(ally,sim.players[0]);sim.resolve_entry_triggers(pending,ally)
        self.assertTrue(sim.stack.items)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertNotIn(source,sim.players[0].battlefield)
        sim.invariant()
