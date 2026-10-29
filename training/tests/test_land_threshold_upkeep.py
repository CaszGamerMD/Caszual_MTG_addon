"""Conditional upkeep events test requirements both when triggered and resolved."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class LandThresholdUpkeepChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def land_count(self,sim,n):
        player=sim.players[0]
        lands=[p for p in player.battlefield if p.card.kind=='land']
        for land in lands[n:]:
            player.battlefield.remove(land)
            player.library.append(land.card)
        self.assertEqual(sim.controlled_land_count(0),n)

    def upkeep(self,sim):
        sim.phase='untap'
        sim.stack.active=sim.active
        sim.stack.priority=sim.active
        sim.step()

    def dragons(self,sim):
        return [p for p in sim.players[0].battlefield if p.card.is_token and p.card.name=='Dragon']

    def test_actual_and_renamed_card_compile_all_conditional_text(self):
        raw=dict(self.lookup['Dragonmaster Outcast'],name='Unfamiliar dragon keeper')
        card=s.import_diagnostic_card(self.rules,raw,0,'keeper',{'Red'})
        self.assertEqual(card.kind,'creature')
        trigger=card.event_definition.triggers[0]
        self.assertEqual(trigger.lands_controlled_at_least,6)
        self.assertEqual((trigger.event,trigger.effect.operation),('upkeep','create_tokens'))
        raw['oracleText']+='\nWhenever you dream, create an impossibility.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_with_five_lands_no_trigger_ever_queued(self):
        sim,cards=self.fixture(['Dragonmaster Outcast'])
        self.put(sim,cards['Dragonmaster Outcast'])
        self.land_count(sim,5)
        self.upkeep(sim)
        self.assertFalse(sim.stack.items)
        self.assertFalse(self.dragons(sim))
        sim.invariant()

    def test_with_six_lands_queues_5_5_flying_dragon(self):
        sim,cards=self.fixture(['Dragonmaster Outcast'])
        self.put(sim,cards['Dragonmaster Outcast'])
        self.land_count(sim,6)
        self.upkeep(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.assertFalse(self.dragons(sim))
        self.drain(sim)
        self.assertEqual(len(self.dragons(sim)),1)
        dragon=self.dragons(sim)[0]
        self.assertEqual((dragon.card.power,dragon.card.toughness),(5,5))
        self.assertIn('flying',dragon.card.traits)
        sim.invariant()

    def test_land_count_is_rechecked_as_trigger_resolves(self):
        sim,cards=self.fixture(['Dragonmaster Outcast'])
        self.put(sim,cards['Dragonmaster Outcast'])
        self.land_count(sim,6)
        self.upkeep(sim)
        self.land_count(sim,5)
        self.drain(sim)
        self.assertFalse(self.dragons(sim))
        self.assertTrue(any(e['kind']=='condition_failed' for e in sim.events))
        sim.invariant()

    def test_source_can_leave_after_trigger_without_preventing_effect(self):
        sim,cards=self.fixture(['Dragonmaster Outcast'])
        source=self.put(sim,cards['Dragonmaster Outcast'])
        self.land_count(sim,6)
        self.upkeep(sim)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(len(self.dragons(sim)),1)
        sim.invariant()

    def test_token_doubling_applies_after_upkeep_condition(self):
        sim,cards=self.fixture(['Dragonmaster Outcast','Doubling Season'])
        for item in cards.values():self.put(sim,item)
        self.land_count(sim,6)
        self.upkeep(sim);self.drain(sim)
        self.assertEqual(len(self.dragons(sim)),2)
        sim.invariant()

    def test_opponents_upkeep_does_not_trigger_and_numeric_threshold_varies(self):
        sim,cards=self.fixture(['Dragonmaster Outcast'])
        self.put(sim,cards['Dragonmaster Outcast'])
        sim.active=1
        self.upkeep(sim)
        self.assertFalse(sim.stack.items)
        raw=dict(self.lookup['Dragonmaster Outcast'],name='Unfamiliar high threshold')
        raw['oracleText']=raw['oracleText'].replace('six or more','nine or more')
        altered=s.import_diagnostic_card(self.rules,raw,0,'modified',{'Red'})
        self.assertEqual(altered.event_definition.triggers[0].lands_controlled_at_least,9)
        sim.invariant()
