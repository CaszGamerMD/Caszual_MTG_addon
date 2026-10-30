"""Destiny-style counterspell immunity and real targeted X/X land animations."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

NAME='Destiny Spinner'

class SessionLearningLandAnimation(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain

    def build(self):
        sim,cards=self.fixture([NAME])
        source=self.put(sim,cards[NAME])
        land=next(p for p in sim.players[0].battlefield if p.card.kind=='land')
        return sim,source,land

    def test_actual_unseen_parameters_and_unknown_clauses(self):
        raw=dict(self.lookup[NAME])
        card=s.import_diagnostic_card(self.rules,raw,0,'real',{'Green'})
        self.assertNotEqual(card.kind,'unsupported',repr(raw['oracleText']))
        self.assertEqual(card.event_definition.protected_spell_types,('creature','enchantment'))
        self.assertEqual(card.event_definition.animate_land_ability,('{3}{G}','Elemental','Enchantment'))
        raw['name']='Unseen Immovable Landweaver'
        raw['oracleText']=raw['oracleText'].replace('{3}{G}','{2}{G}').replace(
            'Elemental creature','Goblin creature').replace('enchantments you control','artifacts you control')
        variant=s.import_diagnostic_card(self.rules,raw,0,'variant',{'Green'})
        self.assertNotEqual(variant.kind,'unsupported')
        self.assertEqual(variant.event_definition.animate_land_ability,('{2}{G}','Goblin','Artifact'))
        raw['oracleText']+='\nDraw unknown cards.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')

    def test_ability_pays_before_stack_and_uses_count_at_resolution(self):
        sim,source,land=self.build()
        self.assertTrue(any(c.kind=='activate_land_animation' and c.target_permanent==land.card.id
                            for c in sim.land_animation_choices(0)))
        sim.activate_land_animation(0,source.card.id,land.card.id)
        self.assertEqual(len(sim.stack.items),1)
        self.assertIsNone(land.temporary_land_power)
        self.drain(sim)
        self.assertEqual(land.temporary_land_power,1)
        g=sim.event_game('main')
        self.assertTrue(g.creature(g.battlefield[land.card.id]))
        self.assertEqual(g.stats(g.battlefield[land.card.id]),(1,1))
        self.assertTrue(g.has(g.battlefield[land.card.id],'haste'))
        self.assertTrue(g.has(g.battlefield[land.card.id],'trample'))
        self.assertIn('Land',g.battlefield[land.card.id].definition.types)
        sim.invariant()

    def test_animation_ends_at_cleanup_without_changing_land_identity(self):
        sim,source,land=self.build()
        sim.activate_land_animation(0,source.card.id,land.card.id);self.drain(sim)
        sim.phase='cleanup'
        sim.step()
        self.assertIsNone(land.temporary_land_power)
        self.assertFalse(sim.event_game('main').creature(sim.event_game('main').battlefield[land.card.id]))
        sim.invariant()

    def test_target_losing_legality_fizzles(self):
        sim,source,land=self.build()
        sim.activate_land_animation(0,source.card.id,land.card.id)
        sim.send_to_destination(sim.players[0],land)
        self.drain(sim)
        self.assertTrue(any(event['kind']=='animate_land_fizzle' for event in sim.events))
        sim.invariant()

    def test_creature_and_enchantment_spells_cannot_be_countered(self):
        sim,source,land=self.build()
        player=sim.players[0]
        spell=next(card for card in player.library if card.kind=='creature')
        player.library.remove(spell)
        frame=sim.stack.push(0,({'operation':'spell','controller':0},spell),spell.name)
        self.assertIsNone(sim.counter_stack_item(frame))
        self.assertIn(frame,sim.stack.items)
        sim.send_to_destination(player,source)
        self.assertIsNotNone(sim.counter_stack_item(frame))
        self.assertIn(spell,player.graveyard)
        sim.invariant()
