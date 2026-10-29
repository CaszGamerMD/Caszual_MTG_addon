"""Serra Ascendant and name-independent life threshold static effects."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from oracle_abilities import compile_abilities


class LifeThresholdStatsChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put

    def with_serra(self):
        sim,cards=self.fixture(['Serra Ascendant'])
        source=self.put(sim,cards['Serra Ascendant'])
        return sim,source

    def test_at_or_above_30_grants_both_stats_and_flying(self):
        sim,source=self.with_serra()
        effective=sim.effective_card(source)
        self.assertEqual((effective.power,effective.toughness),(6,6))
        self.assertIn('flying',effective.traits)
        self.assertIn('lifelink',effective.traits)
        sim.invariant()

    def test_below_threshold_loses_only_conditional_bonuses(self):
        sim,source=self.with_serra()
        sim.players[0].life=29
        effective=sim.effective_card(source)
        self.assertEqual((effective.power,effective.toughness),(1,1))
        self.assertNotIn('flying',effective.traits)
        self.assertIn('lifelink',effective.traits)
        sim.invariant()

    def test_exact_threshold_refreshes_without_a_new_entry(self):
        sim,source=self.with_serra()
        sim.players[0].life=29
        sim.gain_life(0,1)
        self.assertEqual(sim.effective_card(source).power,6)
        self.assertIn('flying',sim.effective_card(source).traits)
        sim.players[0].life-=1
        self.assertEqual(sim.effective_card(source).power,1)
        self.assertNotIn('flying',sim.effective_card(source).traits)
        sim.invariant()

    def test_condition_uses_source_controller_not_opponent(self):
        sim,source=self.with_serra()
        sim.players[0].life=29
        sim.players[1].life=40
        self.assertEqual(sim.effective_card(source).power,1)
        sim.players[0].battlefield.remove(source)
        sim.players[1].battlefield.append(source)
        self.assertEqual(sim.effective_card(source).power,6)
        sim.invariant()

    def test_unseen_name_and_different_threshold_and_keyword(self):
        raw=dict(self.lookup['Serra Ascendant'])
        raw['name']='Unfamiliar ascending creature'
        resolved=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertEqual(resolved.kind,'creature')
        self.assertEqual(len(resolved.event_definition.static_effects),2)
        self.assertEqual({e.life_min for e in resolved.event_definition.static_effects},{30})
        raw['oracleText']+='\nWhen you do a somersault, draw two cards.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        unknown=compile_abilities(
            'As long as you have 12 or more life, this creature gets +3/+2 and has reach.')
        self.assertIsNotNone(unknown)
        self.assertEqual({e.life_min for e in unknown.static_effects},{12})
        self.assertEqual({e.grant for e in unknown.static_effects},{'', 'reach'})
        self.assertIsNone(compile_abilities(
            'As long as you have 12 or more life, this creature gets +3/+2 and has flying and imaginary.'))
