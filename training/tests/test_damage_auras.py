"""Whole-text damage Aura rules: Spirit Link, Keen Sense and Armadillo Cloak."""
import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as base

class AuraDamageChecks(unittest.TestCase):
    setUpClass=classmethod(base.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.EnchantmentChecks.tearDownClass.__func__)
    fixture=base.EnchantmentChecks.fixture
    put=base.EnchantmentChecks.put
    token=base.EnchantmentChecks.token
    drain=base.EnchantmentChecks.drain
    ready=base.EnchantmentChecks.ready
    damage=base.EnchantmentChecks.damage

    def test_real_cards_and_renamed_equivalent_fail_closed_on_unknown_rules(self):
        for name in ('Spirit Link','Keen Sense','Armadillo Cloak'):
            raw=dict(self.lookup[name],name='Unseen enchantment')
            aura=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White','Green'})
            self.assertEqual(aura.kind,'aura',name)
            self.assertTrue(aura.event_definition.damage_events,name)
            raw['oracleText']+='\nWhenever a mouse clicks, draw three cards.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White','Green'}).kind,'unsupported')

    def test_spirit_link_is_stack_trigger_not_lifelink(self):
        sim,cards=self.fixture(['Spirit Link'])
        attacker=self.token(sim,'attacker',power=3,toughness=3)
        self.put(sim,cards['Spirit Link'],attacker.card.id)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(sim.players[0].life,40)
        self.assertEqual(sim.players[1].life,37)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,43)
        self.assertEqual(sim.life_gained_turn[0],3)
        sim.invariant()

    def test_spirit_link_on_opponent_creature_gains_aura_controllers_life(self):
        sim,cards=self.fixture(['Spirit Link'])
        enemy=self.token(sim,'enemy',seat=1,power=3,toughness=3)
        self.put(sim,cards['Spirit Link'],enemy.card.id)
        sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
        sim.declare_attackers([enemy.card.id])
        sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual([p.life for p in sim.players],[37,40])
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[40,40])
        sim.invariant()

    def test_damage_to_blocker_triggers_spirit_link(self):
        sim,cards=self.fixture(['Spirit Link'])
        attacker=self.token(sim,'attacker',power=4,toughness=4)
        self.token(sim,'blocker',seat=1,power=1,toughness=2)
        self.put(sim,cards['Spirit Link'],attacker.card.id)
        self.ready(sim);sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({attacker.card.id:['blocker']})
        sim.group_damage_step()
        self.assertEqual(sim.players[1].life,40)
        self.assertEqual(sim.players[0].life,40)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,44)
        sim.invariant()

    def test_keensense_optional_draw_uses_aura_controller(self):
        sim,cards=self.fixture(['Keen Sense'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        self.put(sim,cards['Keen Sense'],attacker.card.id)
        before=len(sim.players[0].hand)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertEqual(len(sim.players[0].hand),before)
        self.assertEqual(sim.stack.items[-1].payload[0]['operation'],'draw_cards')
        self.assertTrue(sim.stack.items[-1].payload[0]['optional'])
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()

    def test_keensense_does_not_trigger_when_controller_is_damaged(self):
        sim,cards=self.fixture(['Keen Sense'])
        enemy=self.token(sim,'enemy',seat=1,power=2,toughness=2)
        self.put(sim,cards['Keen Sense'],enemy.card.id)
        sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
        sim.declare_attackers([enemy.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        self.assertFalse(sim.stack.items)
        self.assertEqual([p.life for p in sim.players],[38,40])
        sim.invariant()

    def test_double_strike_gives_separate_trigger_each_damage_step(self):
        sim,cards=self.fixture(['Spirit Link','Keen Sense'])
        attacker=self.token(sim,'attacker',power=2,toughness=2,keywords=('double strike',))
        self.put(sim,cards['Spirit Link'],attacker.card.id)
        self.put(sim,cards['Keen Sense'],attacker.card.id)
        before=len(sim.players[0].hand)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        self.damage(sim)
        self.assertEqual(sim.players[0].life,44)
        self.assertEqual(sim.players[1].life,36)
        self.assertEqual(len(sim.players[0].hand),before+2)
        sim.invariant()

    def test_losing_aura_after_damage_does_not_remove_queued_trigger(self):
        sim,cards=self.fixture(['Spirit Link'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        aura=self.put(sim,cards['Spirit Link'],attacker.card.id)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step()
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,42)
        sim.invariant()

    def test_armadillo_cloak_stat_bonus_and_lifegain_stack(self):
        sim,cards=self.fixture(['Armadillo Cloak'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        self.put(sim,cards['Armadillo Cloak'],attacker.card.id)
        stats=sim.effective_card(attacker)
        self.assertEqual((stats.power,stats.toughness),(4,4))
        self.assertIn('trample',stats.traits)
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        sim.group_damage_step();self.drain(sim)
        self.assertEqual(sim.players[0].life,44)
        sim.invariant()
