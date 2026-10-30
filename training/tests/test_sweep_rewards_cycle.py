"""Rewarded sweep destroys only actual creatures and creates usable Treasure artifacts."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f

class SweepRewardsCycle(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    drain=f.EnchantmentChecks.drain

    def treasures(self,sim,seat=0):
        return [p for p in sim.players[seat].battlefield if p.card.is_token and
                p.card.event_definition and 'Treasure' in p.card.event_definition.subtypes]

    def test_full_oracle_unseen_name_quantity_and_unknown_clause(self):
        raw=dict(self.lookup['Blood Money'],name='Unknown harvest')
        c=s.import_diagnostic_card(self.rules,raw,0,'sweep',{'Black'})
        self.assertEqual(c.removal,'destroy_creatures_reward')
        self.assertEqual(c.sweep_reward,(True,1,True))
        raw['oracleText']=raw['oracleText'].replace('a tapped Treasure token','two Treasure tokens')
        c=s.import_diagnostic_card(self.rules,raw,0,'two',{'Black'})
        self.assertEqual(c.sweep_reward,(True,2,False))
        raw['oracleText']+='\nDraw a mystery card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Black'}).kind,'unsupported')
        raw['oracleText']='Destroy all creatures. For each nontoken creature destroyed this way, you create a Treasure tokens.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad2',{'Black'}).kind,'unsupported')

    def test_stack_counts_only_nontoken_actually_destroyed(self):
        sim,cards=self.fixture(['Blood Money','Skirk Prospector'])
        normal=self.put(sim,cards['Skirk Prospector'])
        self.token(sim,'creature-token',seat=1)
        safe=self.token(sim,'indestructible',seat=1,keywords=('indestructible',))
        sim.cast_spell(0,cards['Blood Money'])
        self.assertFalse(self.treasures(sim))
        self.drain(sim)
        self.assertNotIn(normal,sim.players[0].battlefield)
        self.assertIn(safe,sim.players[1].battlefield)
        self.assertEqual(len(self.treasures(sim)),1)
        self.assertTrue(self.treasures(sim)[0].tapped)
        self.assertEqual(self.treasures(sim)[0].card.kind,'artifact')
        sim.invariant()

    def test_treasure_doubler_and_mana_ability(self):
        sim,cards=self.fixture(['Blood Money','Skirk Prospector','Doubling Season'])
        self.put(sim,cards['Doubling Season'])
        self.put(sim,cards['Skirk Prospector'])
        sim.cast_spell(0,cards['Blood Money']);self.drain(sim)
        self.assertEqual(len(self.treasures(sim)),2)
        token=self.treasures(sim)[0]
        with self.assertRaises(ValueError):sim.activate_treasure_mana(0,token.card.id,3)
        token.tapped=False
        with self.assertRaises(ValueError):sim.activate_treasure_mana(1,token.card.id,3)
        sim.activate_treasure_mana(0,token.card.id,3)
        self.assertEqual(sim.players[0].mana_pool[3],1)
        self.assertEqual(len(self.treasures(sim)),1)
        self.assertTrue(s.mana_pool.plan('{R}',sim.players[0].mana_pool,[])['paid'])
        sim.invariant()

    def test_zero_destroyed_means_zero_treasures(self):
        sim,cards=self.fixture(['Blood Money'])
        self.token(sim,'only-token')
        sim.cast_spell(0,cards['Blood Money']);self.drain(sim)
        self.assertFalse(self.treasures(sim))
        sim.invariant()
