"""Optional upkeep token creation plus independent creature-color anthems."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class OptionalUpkeepTokenChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def upkeep(self,sim):
        sim.phase='untap'
        sim.stack.active=sim.active
        sim.stack.priority=sim.active
        sim.step()

    def worms(self,sim):
        return [p for p in sim.players[0].battlefield
                if p.card.is_token and p.card.name=='Worm']

    def test_unknown_creature_name_uses_unchanged_complete_oracle_rule(self):
        raw=dict(self.lookup['Creakwood Liege'],name='Unknown dual-color liege')
        card=s.import_diagnostic_card(self.rules,raw,0,'liege',{'Green','Black'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.static_effects),2)
        self.assertEqual(card.event_definition.triggers[0].event,'upkeep')
        self.assertTrue(card.event_definition.triggers[0].effect.optional)
        raw['oracleText']+='\nWhenever a tree dances, invent a permanent.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_optional_upkeep_trigger_waits_on_priority_stack(self):
        sim,cards=self.fixture(['Creakwood Liege'])
        self.put(sim,cards['Creakwood Liege'])
        self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.assertFalse(self.worms(sim))
        self.drain(sim)
        self.assertEqual(len(self.worms(sim)),1)
        self.assertEqual(self.worms(sim)[0].card.event_definition.colors,
                         frozenset({'Black','Green'}))
        sim.invariant()

    def test_declining_a_may_create_trigger_produces_no_tokens(self):
        sim,cards=self.fixture(['Creakwood Liege'])
        self.put(sim,cards['Creakwood Liege'])
        self.upkeep(sim)
        with patch.object(sim,'choose_optional_token_creation',return_value=False):
            self.drain(sim)
        self.assertFalse(self.worms(sim))
        self.assertTrue(any(e['kind']=='token_creation_declined' for e in sim.events))
        sim.invariant()

    def test_continuous_black_and_green_buffs_stack_on_dual_color_worm(self):
        sim,cards=self.fixture(['Creakwood Liege'])
        source=self.put(sim,cards['Creakwood Liege'])
        self.upkeep(sim);self.drain(sim)
        worm=self.worms(sim)[0]
        self.assertEqual((sim.effective_card(worm).power,sim.effective_card(worm).toughness),(3,3))
        self.assertEqual((sim.effective_card(source).power,sim.effective_card(source).toughness),(2,2))
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual((sim.effective_card(worm).power,sim.effective_card(worm).toughness),(1,1))
        sim.invariant()

    def test_token_doubler_multiplies_accepted_upkeep_creation_once(self):
        sim,cards=self.fixture(['Creakwood Liege','Parallel Lives'])
        for card in cards.values():self.put(sim,card)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(len(self.worms(sim)),2)
        self.assertTrue(all(sim.effective_card(p).power==3 for p in self.worms(sim)))
        sim.invariant()

    def test_optional_creation_triggers_token_watchers_after_replacements(self):
        sim,cards=self.fixture(['Creakwood Liege','Parallel Lives','Mirkwood Bats'])
        for card in cards.values():self.put(sim,card)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(len(self.worms(sim)),2)
        self.assertEqual(sim.players[1].life,38)
        sim.invariant()

    def test_only_source_controllers_upkeep_queues_own_trigger(self):
        sim,cards=self.fixture(['Creakwood Liege'])
        self.put(sim,cards['Creakwood Liege'])
        sim.active=1
        self.upkeep(sim)
        self.assertFalse(sim.stack.items)
        self.assertFalse(self.worms(sim))
        sim.invariant()
