"""Reusable life-gain replacement effects, including stacked doublers."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as base
from oracle_abilities import compile_abilities

class LifeReplacementChecks(unittest.TestCase):
    setUpClass=classmethod(base.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.EnchantmentChecks.tearDownClass.__func__)
    fixture=base.EnchantmentChecks.fixture
    put=base.EnchantmentChecks.put
    token=base.EnchantmentChecks.token
    drain=base.EnchantmentChecks.drain

    def test_real_names_and_unfamiliar_names_compile_without_ignoring_rules(self):
        for name in ('Boon Reflection','Rhox Faithmender'):
            raw=dict(self.lookup[name],name='Unfamiliar replacement')
            card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'White'})
            self.assertNotEqual(card.kind,'unsupported')
            self.assertEqual(card.event_definition.life_multiplier,2)
            raw['oracleText']+='\nIf you would cast cards for free, create ten treasures.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'If you would gain life, you gain twice that much life instead.\nDraw an unknown token.'))

    def test_one_multiplier_doubles_gains_not_losses(self):
        sim,cards=self.fixture(['Boon Reflection'])
        self.put(sim,cards['Boon Reflection'])
        sim.gain_life(0,3)
        self.assertEqual(sim.players[0].life,46)
        self.assertEqual(sim.life_gained_turn,[6,0])
        sim.players[0].life-=7
        self.assertEqual(sim.players[0].life,39)
        self.assertEqual(sim.life_gained_turn[0],6)
        sim.invariant()

    def test_two_independent_multipliers_stack_and_stop_after_leaving(self):
        sim,cards=self.fixture(['Boon Reflection','Rhox Faithmender'])
        boon=self.put(sim,cards['Boon Reflection'])
        self.put(sim,cards['Rhox Faithmender'])
        sim.gain_life(0,2)
        self.assertEqual(sim.players[0].life,48)
        self.assertEqual(sim.life_gained_turn[0],8)
        sim.send_to_destination(sim.players[0],boon)
        sim.gain_life(0,2)
        self.assertEqual(sim.players[0].life,52)
        self.assertEqual(sim.life_gained_turn[0],12)
        sim.invariant()

    def test_opponents_life_gains_are_not_modified(self):
        sim,cards=self.fixture(['Boon Reflection'])
        self.put(sim,cards['Boon Reflection'])
        sim.gain_life(1,3)
        self.assertEqual([p.life for p in sim.players],[40,43])
        self.assertEqual(sim.life_gained_turn,[0,3])
        sim.invariant()

    def test_triggered_lifegain_is_replaced_and_meets_griffin_threshold(self):
        sim,cards=self.fixture(['Boon Reflection','Ajani\'s Welcome','Griffin Aerie'])
        for name in ('Boon Reflection','Ajani\'s Welcome','Griffin Aerie'):
            self.put(sim,cards[name])
        self.token(sim,'first-creature')
        self.token(sim,'second-creature')
        # Token helper enters directly; manually collect ordinary ETB triggers.
        # Use an additional creature to ensure ordinary entry lifegain is exercised.
        c=s.Card('entry','Unfamiliar arrival','creature',power=2,toughness=2,is_token=True)
        pending=sim.enter_creature(c,sim.players[0])
        sim.resolve_entry_triggers(pending,c)
        self.drain(sim)
        self.assertEqual(sim.life_gained_turn[0],2)
        sim.gain_life(0,1)
        self.assertEqual(sim.life_gained_turn[0],4)
        sim.phase='end_step';sim.step();self.drain(sim)
        self.assertTrue(any('Griffin' in p.card.name for p in sim.players[0].battlefield))
        sim.invariant()

    def test_rhox_lifelink_is_replaced(self):
        sim,cards=self.fixture(['Rhox Faithmender'])
        rhox=self.put(sim,cards['Rhox Faithmender'])
        rhox.fresh=False
        sim.phase='attack';sim.declare_attackers([rhox.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(sim.players[0].life,42)
        self.assertEqual(sim.life_gained_turn[0],2)
        sim.invariant()
