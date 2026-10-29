"""Non-targeted creature sweeps retain rules for indestructible and dynamic toughness."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class CreatureSweepChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def sweep(self,sim,card):
        sim.cast_spell(0,card)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)

    def test_real_damnation_and_citywide_bust_compile_without_card_names(self):
        for name,operation in (('Damnation','destroy_all_creatures'),
                               ('Citywide Bust','destroy_toughness_4')):
            raw=dict(self.lookup[name],name='Unknown board sweep')
            card=s.import_diagnostic_card(self.rules,raw,0,'sweep',{'Black','White'})
            self.assertEqual((card.kind,card.removal),('removal_spell',operation))
            raw['oracleText']+='\nEach player creates an unknown Mystery.'
            self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_damnation_destoys_both_players_creature_tokens(self):
        sim,cards=self.fixture(['Damnation'])
        own=self.token(sim,'own')
        enemy=self.token(sim,'enemy',seat=1)
        self.sweep(sim,cards['Damnation'])
        self.assertFalse(any(p.card.id==own.card.id for p in sim.players[0].battlefield))
        self.assertFalse(any(p.card.id==enemy.card.id for p in sim.players[1].battlefield))
        self.assertIn(cards['Damnation'],sim.players[0].graveyard)
        sim.invariant()

    def test_damnation_does_not_destroy_indestructible_and_ignores_hexproof(self):
        sim,cards=self.fixture(['Damnation'])
        safe=self.token(sim,'safe',seat=1,keywords=('indestructible',))
        shield=self.token(sim,'shield',seat=1,keywords=('hexproof',))
        own=self.token(sim,'own')
        self.sweep(sim,cards['Damnation'])
        self.assertTrue(any(p.card.id==safe.card.id for p in sim.players[1].battlefield))
        self.assertFalse(any(p.card.id==shield.card.id for p in sim.players[1].battlefield))
        self.assertFalse(any(p.card.id==own.card.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_citywide_bust_sweeps_4_toughness_and_higher(self):
        sim,cards=self.fixture(['Citywide Bust'])
        low=self.token(sim,'low',power=3,toughness=3)
        threshold=self.token(sim,'threshold',power=1,toughness=4)
        high=self.token(sim,'high',seat=1,power=1,toughness=8)
        self.sweep(sim,cards['Citywide Bust'])
        self.assertTrue(any(p.card.id==low.card.id for p in sim.players[0].battlefield))
        self.assertFalse(any(p.card.id==threshold.card.id for p in sim.players[0].battlefield))
        self.assertFalse(any(p.card.id==high.card.id for p in sim.players[1].battlefield))
        sim.invariant()

    def test_toughness_is_dynamic_at_resolution_including_counters(self):
        sim,cards=self.fixture(['Citywide Bust'])
        threshold=self.token(sim,'growing',power=3,toughness=3)
        threshold.counters=1
        sim.cast_spell(0,cards['Citywide Bust'])
        self.assertIn(threshold,sim.players[0].battlefield)
        self.drain(sim)
        self.assertNotIn(threshold,sim.players[0].battlefield)
        sim.invariant()

    def test_changes_in_response_can_move_target_out_of_sweep(self):
        sim,cards=self.fixture(['Citywide Bust'])
        growing=self.token(sim,'original',power=2,toughness=4)
        sim.cast_spell(0,cards['Citywide Bust'])
        growing.temporary_toughness=-1
        self.drain(sim)
        self.assertIn(growing,sim.players[0].battlefield)
        sim.invariant()

    def test_noncreatures_are_not_destroyed_by_creature_sweep(self):
        sim,cards=self.fixture(['Damnation','Parallel Lives'])
        enchant=cards['Parallel Lives']
        sim.players[0].hand.remove(enchant)
        sim.enter_creature(enchant,sim.players[0])
        self.sweep(sim,cards['Damnation'])
        self.assertTrue(any(p.card.id==enchant.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_empty_board_is_legal_spell_not_target_error(self):
        sim,cards=self.fixture(['Citywide Bust'])
        self.sweep(sim,cards['Citywide Bust'])
        self.assertIn(cards['Citywide Bust'],sim.players[0].graveyard)
        sim.invariant()
