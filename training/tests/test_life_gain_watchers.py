"""Whole-text life-gain trigger grammar and once-per-event stack behavior."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class LifeGainWatcherChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def flush(self,sim):
        sim.resolve_entry_triggers([],s.Card('life-event','Life event','spell'))
        self.drain(sim)

    def test_renamed_original_and_extra_unknown_instruction_fail_closed(self):
        raw=dict(self.lookup['Marauding Blight-Priest'],name='Unfamiliar life watcher')
        card=s.import_diagnostic_card(self.rules,raw,0,'watcher',{'Black'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.triggers),1)
        trigger=card.event_definition.triggers[0]
        self.assertEqual((trigger.event,trigger.effect.operation,trigger.effect.amount),
                         ('gain_life','lose_life',1))
        raw['oracleText']+='\nWhenever you invent a spell, conjure a surprise.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'invalid',{'Black'}).kind,'unsupported')

    def test_single_large_gain_is_one_event_not_one_trigger_per_life(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        self.put(sim,cards['Marauding Blight-Priest'])
        sim.gain_life(0,7)
        self.assertEqual([p.life for p in sim.players],[47,40])
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[47,39])
        sim.invariant()

    def test_separate_gain_events_trigger_independently(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        self.put(sim,cards['Marauding Blight-Priest'])
        sim.gain_life(0,1);sim.gain_life(0,3)
        sim.resolve_entry_triggers([],s.Card('life-event','Life event','spell'))
        self.assertEqual(len(sim.stack.items),2)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[44,38])
        sim.invariant()

    def test_replacement_double_gain_still_one_trigger(self):
        sim,cards=self.fixture(['Marauding Blight-Priest','Boon Reflection'])
        for card in cards.values():self.put(sim,card)
        sim.gain_life(0,3)
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[46,39])
        self.assertEqual(sim.life_gained_turn[0],6)
        sim.invariant()

    def test_two_watchers_each_trigger_once_per_gain_event(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        original=self.put(sim,cards['Marauding Blight-Priest'])
        other=s.Card('second-watcher','Another watcher','creature',power=3,toughness=2,
                     event_definition=original.card.event_definition,is_token=True)
        sim.enter_creature(other,sim.players[0])
        sim.gain_life(0,2)
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[42,38])
        sim.invariant()

    def test_opponent_gaining_life_does_not_trigger_my_watcher(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        self.put(sim,cards['Marauding Blight-Priest'])
        sim.gain_life(1,4)
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[40,44])
        sim.invariant()

    def test_zero_gain_and_life_loss_are_not_events(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        self.put(sim,cards['Marauding Blight-Priest'])
        sim.gain_life(0,0)
        sim.players[0].life-=5
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[35,40])
        sim.invariant()

    def test_queued_trigger_survives_watcher_leaving_battlefield(self):
        sim,cards=self.fixture(['Marauding Blight-Priest'])
        watcher=self.put(sim,cards['Marauding Blight-Priest'])
        sim.gain_life(0,1)
        sim.send_to_destination(sim.players[0],watcher)
        self.flush(sim)
        self.assertEqual([p.life for p in sim.players],[41,39])
        sim.invariant()

    def test_nightblade_lifegain_queues_independent_priest_trigger(self):
        sim,cards=self.fixture(["Nadier's Nightblade",'Marauding Blight-Priest'])
        for card in cards.values():self.put(sim,card)
        squirrel=self.token(sim,'squirrel')
        sim.sacrifice_token(0,squirrel.card.id)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[41,38])
        sim.invariant()
