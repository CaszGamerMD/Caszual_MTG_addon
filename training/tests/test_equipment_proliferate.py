"""Sword of Truth and Justice composes a non-targeted counter and proliferate sequence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class EquipmentProliferateChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready
    damage=fixtures.EnchantmentChecks.damage

    def test_real_and_renamed_card_compile_all_clauses_and_reject_extra_text(self):
        raw=dict(self.lookup['Sword of Truth and Justice'])
        card=s.import_diagnostic_card(self.rules,raw,0,'truth-justice',{'Red'})
        self.assertEqual(card.kind,'equipment')
        self.assertEqual(card.event_definition.equipped_player_hit_steps,
                         (('counter_controlled_creature',1,None),('proliferate',0,None)))
        self.assertEqual(card.event_definition.attachment[3:5],(2,2))
        self.assertEqual(card.event_definition.attachment[2],
                         frozenset({'protection from white','protection from blue'}))

        raw['name']='Unfamiliar Counter and Growth Blade'
        renamed=s.import_diagnostic_card(self.rules,raw,0,'renamed-truth-justice',{'Red'})
        self.assertEqual(renamed.kind,'equipment')
        self.assertEqual(renamed.event_definition.equipped_player_hit_steps,
                         card.event_definition.equipped_player_hit_steps)

        raw['oracleText']+='\nDraw an extra card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unsupported-truth-justice',{'Red'}).kind,
                         'unsupported')

    def test_combat_hit_counters_a_creature_then_proliferates_existing_counters(self):
        sim,cards=self.fixture(['Sword of Truth and Justice'])
        attacker=self.token(sim,'truth-attacker',power=3,toughness=3)
        already_countered=self.token(sim,'truth-ally',power=1,toughness=1)
        already_countered.counters=1
        sword=self.put(sim,cards['Sword of Truth and Justice'])

        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        self.damage(sim)

        # The controller's first creature choice happens during resolution.
        # Its new counter is then eligible for the subsequent proliferate step.
        self.assertEqual(attacker.counters,2)
        self.assertEqual(already_countered.counters,2)
        self.assertEqual(sim.players[1].life,35)
        sim.invariant()

    def test_trigger_has_no_target_and_survives_equipment_leaving(self):
        sim,cards=self.fixture(['Sword of Truth and Justice'])
        attacker=self.token(sim,'truth-surviving-attacker',power=2,toughness=2)
        ally=self.token(sim,'truth-surviving-ally',power=1,toughness=1)
        sword=self.put(sim,cards['Sword of Truth and Justice'])
        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        sim.group_damage_step()

        trigger=next(item.payload[0] for item in sim.stack.items
                     if item.payload[0].get('operation')=='equipment_hit_sequence')
        self.assertNotIn('target',trigger)
        self.assertTrue(all('target' not in step for step in trigger['steps']))
        sim.send_to_destination(sim.players[0],sword)
        self.drain(sim)
        self.assertEqual(attacker.counters,2)
        sim.invariant()

    def test_proliferate_can_finish_an_opponent_with_ten_poison_counters(self):
        sim,cards=self.fixture(['Sword of Truth and Justice'])
        attacker=self.token(sim,'truth-poison-attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Truth and Justice'])
        sim.players[1].poison_counters=9
        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        self.damage(sim)

        self.assertEqual(sim.players[1].poison_counters,10)
        self.assertTrue(sim.finished)
        self.assertEqual(sim.winner,0)
        sim.invariant()


if __name__=='__main__':
    unittest.main()
