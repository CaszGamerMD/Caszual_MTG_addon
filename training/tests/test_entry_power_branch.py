"""Power-dependent ETB choice: evaluate on stack, apply counter replacements."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class EntryPowerBranchChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def enter(self,sim,identifier,seat=0,power=2,toughness=2):
        definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(),False,
                                     power,toughness,frozenset())
        card=s.Card(identifier,identifier,'creature','{0}',f'{power};{toughness};',
                    power,toughness,event_definition=definition,is_token=True)
        pending=sim.enter_creature(card,sim.players[seat])
        sim.resolve_entry_triggers(pending,card)
        return next(p for p in sim.players[seat].battlefield if p.card.id==identifier)

    def test_real_renamed_parameterized_and_unknown_clause(self):
        raw=dict(self.lookup['Tribute to the World Tree'],name='Unseen World Monument')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertNotEqual(card.kind,'unsupported')
        effect=card.event_definition.triggers[0].effect
        self.assertEqual((effect.operation,effect.amount,effect.power_threshold,effect.low_power_counters),
                         ('entry_power_branch',1,3,2))
        raw['oracleText']=raw['oracleText'].replace('draw a card','draw three cards').replace('power is 3','power is 5').replace('put two','put three')
        variant=s.import_diagnostic_card(self.rules,raw,0,'variant',{'Green'})
        self.assertEqual((variant.event_definition.triggers[0].effect.amount,
                          variant.event_definition.triggers[0].effect.power_threshold,
                          variant.event_definition.triggers[0].effect.low_power_counters),(3,5,3))
        raw['oracleText']+='\nAll opponents lose the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_low_power_counter_replacement_and_opponent_filter(self):
        sim,cards=self.fixture(['Tribute to the World Tree','Hardened Scales'])
        self.put(sim,cards['Tribute to the World Tree'])
        self.put(sim,cards['Hardened Scales'])
        enemy=self.enter(sim,'enemy',seat=1,power=1,toughness=2)
        self.assertFalse(sim.stack.items)
        ally=self.enter(sim,'ally',power=2,toughness=2)
        self.assertEqual(ally.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(ally.counters,3)
        self.assertEqual(enemy.counters,0)
        sim.invariant()

    def test_draw_power_checked_on_resolution_and_source_can_leave(self):
        sim,cards=self.fixture(['Tribute to the World Tree'])
        source=self.put(sim,cards['Tribute to the World Tree'])
        ally=self.enter(sim,'ally',power=2,toughness=3)
        before=len(sim.players[0].hand)
        ally.temporary_power+=2
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        self.assertEqual(ally.counters,0)
        sim.invariant()

    def test_last_known_power_updates_when_entrant_leaves_after_being_pumped(self):
        sim,cards=self.fixture(['Tribute to the World Tree'])
        self.put(sim,cards['Tribute to the World Tree'])
        ally=self.enter(sim,'ally',power=2,toughness=3)
        before=len(sim.players[0].hand)
        ally.temporary_power+=2
        sim.send_to_destination(sim.players[0],ally)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_exited_low_power_object_gets_no_counters(self):
        sim,cards=self.fixture(['Tribute to the World Tree'])
        self.put(sim,cards['Tribute to the World Tree'])
        ally=self.enter(sim,'ally',power=2,toughness=3)
        sim.send_to_destination(sim.players[0],ally)
        self.drain(sim)
        self.assertFalse(any(p.card.id==ally.card.id for p in sim.players[0].battlefield))
        sim.invariant()
