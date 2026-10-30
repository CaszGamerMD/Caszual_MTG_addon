"""Creature mana activations are mana abilities (no stack), not free tap spells."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class CreatureManaChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put

    def test_real_and_renamed_fixed_mana_with_parameterized_amount(self):
        for name,count in [('Elvish Mystic',1),('Llanowar Elves',1),('Llanowar Tribe',3)]:
            raw=self.lookup[name]
            card=s.import_diagnostic_card(self.rules,raw,0,'mana-'+name,{'Green'})
            self.assertEqual(card.kind,'creature',name)
            self.assertEqual(card.event_definition.scaled_mana_tap,'fixed:G:'+str(count))
            renamed=dict(raw,name='Unseen Ruby Mystic',oracleText=raw['oracleText'].replace('{G}','{R}'),colors=['Red'],colorIdentity=['Red'])
            other=s.import_diagnostic_card(self.rules,renamed,0,'unseen',{'Red'})
            self.assertEqual(other.event_definition.scaled_mana_tap,'fixed:R:'+str(count))
            bad=dict(renamed,oracleText=renamed['oracleText']+'\nWin the game.')
            self.assertEqual(s.import_diagnostic_card(self.rules,bad,0,'bad',{'Red'}).kind,'unsupported')

    def test_tapping_requires_control_and_summoning_sickness_and_produces_all_mana(self):
        sim,cards=self.fixture(['Llanowar Tribe'])
        tribe=self.put(sim,cards['Llanowar Tribe'])
        self.assertNotIn(tribe.card.id,dict(sim.mana_sources(0)))
        tribe.fresh=False
        self.assertEqual(dict(sim.mana_sources(0))[tribe.card.id],((0,0,0,0,3,0),))
        self.assertNotIn(tribe.card.id,dict(sim.mana_sources(1)))
        sim.stack.priority=0
        before=len(sim.stack.items)
        sim.activate_scaled_mana(0,tribe.card.id,4)
        self.assertEqual(sim.players[0].mana_pool[4],3)
        self.assertEqual(len(sim.stack.items),before)
        self.assertTrue(tribe.tapped)
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,tribe.card.id,4)
        sim.invariant()

    def test_fixed_mana_does_not_allow_off_color_activation(self):
        sim,cards=self.fixture(['Elvish Mystic'])
        elf=self.put(sim,cards['Elvish Mystic']);elf.fresh=False
        sim.stack.priority=0
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,elf.card.id,3)
        self.assertFalse(elf.tapped)
        self.assertEqual(sim.players[0].mana_pool[4],0)
