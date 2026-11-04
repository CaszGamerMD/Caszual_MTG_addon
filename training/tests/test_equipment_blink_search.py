"""Sword of Hearth and Home exercises the owned-creature Equipment target path."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class EquipmentBlinkSearchChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain
    ready=fixtures.EnchantmentChecks.ready

    def hit_trigger(self,sim,attacker):
        self.ready(sim)
        sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({})
        sim.group_damage_step()
        return next(item.payload[0] for item in sim.stack.items
                    if item.payload[0].get('operation')=='equipment_hit_sequence')

    def test_real_renamed_and_unknown_text(self):
        raw=dict(self.lookup['Sword of Hearth and Home'])
        card=s.import_diagnostic_card(self.rules,raw,0,'sword-hearth-home',{'Red'})
        self.assertEqual(card.kind,'equipment')
        self.assertEqual(card.event_definition.equipped_player_hit_steps,
                         (('blink_owned_creature_basic_search',1,None),))
        self.assertEqual(card.event_definition.attachment[3:5],(2,2))
        raw['name']='Unknown Horizon Blade'
        renamed=s.import_diagnostic_card(self.rules,raw,0,'renamed-hearth-home',{'Red'})
        self.assertEqual(renamed.kind,'equipment')
        self.assertEqual(renamed.event_definition.equipped_player_hit_steps,
                         card.event_definition.equipped_player_hit_steps)
        raw['oracleText']+='\nCreate a Treasure token.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown-hearth-home',{'Red'}).kind,
                         'unsupported')

    def test_returns_a_creature_i_own_even_if_opponent_controls_it(self):
        sim,cards=self.fixture(['Sword of Hearth and Home','Elvish Mystic'])
        attacker=self.token(sim,'hearth-attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Hearth and Home'])
        owned=self.put(sim,cards['Elvish Mystic'])
        sim.players[0].battlefield.remove(owned)
        sim.players[1].battlefield.append(owned)
        basic=next(card for card in sim.players[0].library
                   if card.kind=='land' and card.basic_land)
        basic_id=basic.id
        sim.choose_equipment_owned_creature_target=lambda event,candidates: next(
            (pair for pair in candidates if pair[0]==1),None)

        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        trigger=self.hit_trigger(sim,attacker)
        step=trigger['steps'][0]
        self.assertEqual(step['target'],owned.card.id)
        self.assertEqual(step['targetEntry'],owned.entered_at)
        self.drain(sim)

        returned=next(item for item in sim.players[0].battlefield
                      if item.card.id==owned.card.id)
        self.assertFalse(any(item.card.id==owned.card.id for item in sim.players[1].battlefield))
        self.assertNotEqual(returned.entered_at,owned.entered_at)
        land=next(item for item in sim.players[0].battlefield if item.card.id==basic_id)
        self.assertFalse(land.tapped)
        self.assertNotIn(basic_id,{card.id for card in sim.players[0].library})
        sim.invariant()

    def test_illegal_target_fizzles_entire_sequence_before_search(self):
        sim,cards=self.fixture(['Sword of Hearth and Home','Elvish Mystic'])
        attacker=self.token(sim,'hearth-fizzle-attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Hearth and Home'])
        owned=self.put(sim,cards['Elvish Mystic'])
        sim.players[0].battlefield.remove(owned)
        sim.players[1].battlefield.append(owned)
        basic=next(card for card in sim.players[0].library
                   if card.kind=='land' and card.basic_land)
        basic_id=basic.id
        sim.choose_equipment_owned_creature_target=lambda event,candidates: next(
            (pair for pair in candidates if pair[0]==1),None)
        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        trigger=self.hit_trigger(sim,attacker)
        self.assertEqual(trigger['steps'][0]['target'],owned.card.id)
        sim.send_to_destination(sim.players[1],owned)
        self.drain(sim)

        self.assertIn(basic_id,{card.id for card in sim.players[0].library})
        self.assertNotIn(basic_id,{item.card.id for item in sim.players[0].battlefield})
        self.assertTrue(any(card.id==owned.card.id for card in sim.players[0].graveyard))
        sim.invariant()

    def test_up_to_one_target_can_be_declined_without_skipping_land_search(self):
        sim,cards=self.fixture(['Sword of Hearth and Home'])
        attacker=self.token(sim,'hearth-no-target-attacker',power=2,toughness=2)
        sword=self.put(sim,cards['Sword of Hearth and Home'])
        basic=next(card for card in sim.players[0].library
                   if card.kind=='land' and card.basic_land)
        basic_id=basic.id
        sim.choose_equipment_owned_creature_target=lambda event,candidates: None
        sim.activate_equip(0,sword.card.id,attacker.card.id)
        self.drain(sim)
        trigger=self.hit_trigger(sim,attacker)
        self.assertIsNone(trigger['steps'][0]['target'])
        self.drain(sim)
        land=next(item for item in sim.players[0].battlefield if item.card.id==basic_id)
        self.assertFalse(land.tapped)
        self.assertTrue(any(item.card.id==attacker.card.id for item in sim.players[0].battlefield))
        sim.invariant()


if __name__=='__main__':
    unittest.main()
