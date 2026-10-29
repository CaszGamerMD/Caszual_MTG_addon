"""Angel of Vitality, additive gain replacements and threshold-dependent stats."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as base
from oracle_abilities import compile_abilities

class AdditiveLifeChecks(unittest.TestCase):
    setUpClass=classmethod(base.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.EnchantmentChecks.tearDownClass.__func__)
    fixture=base.EnchantmentChecks.fixture
    put=base.EnchantmentChecks.put

    def test_angel_and_unknown_name_compile_with_all_three_clauses(self):
        raw=dict(self.lookup['Angel of Vitality'],name='Unseen lifegain angel')
        card=s.import_diagnostic_card(self.rules,raw,0,'angel',{'White'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.life_addition,1)
        self.assertIn('flying',card.event_definition.abilities)
        self.assertEqual(card.event_definition.static_effects[0].life_min,25)
        raw['oracleText']+='\nWhenever a player jumps, create a secret.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_plus_one_applies_once_to_each_positive_gain_event(self):
        sim,cards=self.fixture(['Angel of Vitality'])
        self.put(sim,cards['Angel of Vitality'])
        sim.gain_life(0,2)
        sim.gain_life(0,3)
        sim.gain_life(0,0)
        self.assertEqual(sim.players[0].life,47)
        self.assertEqual(sim.life_gained_turn[0],7)
        sim.gain_life(1,2)
        self.assertEqual(sim.players[1].life,42)
        sim.invariant()

    def test_stat_bonus_tracks_current_controller_life_at_25(self):
        sim,cards=self.fixture(['Angel of Vitality'])
        angel=self.put(sim,cards['Angel of Vitality'])
        sim.players[0].life=24
        self.assertEqual((sim.effective_card(angel).power,sim.effective_card(angel).toughness),(2,2))
        sim.gain_life(0,1)
        self.assertEqual((sim.effective_card(angel).power,sim.effective_card(angel).toughness),(4,4))
        sim.players[0].life-=2
        self.assertEqual((sim.effective_card(angel).power,sim.effective_card(angel).toughness),(2,2))
        self.assertIn('flying',sim.effective_card(angel).traits)
        sim.invariant()

    def test_adding_before_doubling_is_legal_maximum_gain_order(self):
        sim,cards=self.fixture(['Angel of Vitality','Boon Reflection'])
        for item in cards.values():self.put(sim,item)
        sim.gain_life(0,2)
        self.assertEqual(sim.players[0].life,46)
        self.assertEqual(sim.life_gained_turn[0],6)
        sim.invariant()

    def test_different_threshold_and_increase_are_parsed_not_hardcoded(self):
        program=compile_abilities('Flying\nIf you would gain life, you gain that much life plus 3 instead.\n'
                                  'This creature gets +1/+2 as long as you have 17 or more life.')
        self.assertIsNotNone(program)
        self.assertEqual(program.life_addition,3)
        self.assertEqual(program.static_effects[0].life_min,17)
        self.assertEqual((program.static_effects[0].power,program.static_effects[0].toughness),(1,2))
        self.assertIsNone(compile_abilities('If you would gain life, you gain 10 mysterious tokens instead.'))
