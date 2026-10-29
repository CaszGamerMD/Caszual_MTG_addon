"""Block-power restrictions use current stats and full reusable Oracle clauses."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class BlockerPowerRestrictionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_beloved_princess_and_unfamiliar_numeric_variant_parse_strictly(self):
        raw=dict(self.lookup['Beloved Princess'],name='Unknown evasive creature')
        card=s.import_diagnostic_card(self.rules,raw,0,'princess',{'White'})
        self.assertEqual(card.kind,'creature')
        self.assertIn('lifelink',card.event_definition.abilities)
        self.assertIn('block_power_below_3',card.event_definition.abilities)
        for limit in (1,2,3,7):
            variant=dict(raw,oracleText='Lifelink\nThis creature can\'t be blocked by creatures with power '+str(limit)+' or greater.')
            other=s.import_diagnostic_card(self.rules,variant,0,'changed',set())
            self.assertEqual(other.kind,'creature')
            self.assertIn('block_power_below_'+str(limit),other.event_definition.abilities)
            variant['oracleText']+='\nDraw extra cards.'
            self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',set()).kind,'unsupported')

    def test_current_blocker_power_controls_legality_and_policy(self):
        sim,cards=self.fixture(['Beloved Princess'])
        princess=self.put(sim,cards['Beloved Princess'])
        princess.fresh=False
        small=self.token(sim,'small',seat=1,power=2,toughness=4)
        large=self.token(sim,'large',seat=1,power=3,toughness=4)
        self.assertTrue(sim.can_block(princess,small))
        self.assertFalse(sim.can_block(princess,large))
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([princess.card.id])
        all_choices=sim.group_block_choices(1)
        self.assertFalse(any(large.card.id in ids for choice in all_choices for _,ids in choice.blocks))
        with self.assertRaises(ValueError):sim.declare_blockers({princess.card.id:[large.card.id]})
        sim.declare_blockers({princess.card.id:[small.card.id]})
        sim.invariant()

    def test_buffs_and_debuffs_rechecked_at_block_declaration(self):
        sim,cards=self.fixture(['Beloved Princess'])
        princess=self.put(sim,cards['Beloved Princess'])
        blocker=self.token(sim,'blocker',seat=1,power=2,toughness=3)
        self.assertTrue(sim.can_block(princess,blocker))
        blocker.temporary_power=2
        self.assertFalse(sim.can_block(princess,blocker))
        blocker.temporary_power=-1
        self.assertTrue(sim.can_block(princess,blocker))
        sim.invariant()
