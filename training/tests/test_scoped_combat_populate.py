"""Player-scoped combat prevention composes with non-targeted populate."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helpers


class ScopedCombatPopulateChecks(unittest.TestCase):
    setUpClass=classmethod(helpers.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helpers.EnchantmentChecks.tearDownClass.__func__)
    fixture=helpers.EnchantmentChecks.fixture
    put=helpers.EnchantmentChecks.put
    token=helpers.EnchantmentChecks.token
    damage=helpers.EnchantmentChecks.damage
    drain=helpers.EnchantmentChecks.drain

    def test_real_card_new_name_and_full_clause_compilation(self):
        raw=dict(self.lookup["Druid's Deliverance"],name='Unknown woodland rescue')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'Green'})
        self.assertEqual(card.kind,'prevention_spell')
        self.assertTrue(card.prevent_player_combat_damage)
        self.assertTrue(card.populate)
        self.assertFalse(card.prevent_all_combat_damage)
        raw['oracleText']+='\nDraw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,
                         'unsupported')
        raw['oracleText']='Populate. Prevent all combat damage that would be dealt to you this turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'wrong-order',{'Green'}).kind,
                         'unsupported')

    def test_copies_copiable_values_not_counters_or_tapped_state_and_doubles(self):
        sim,cards=self.fixture(["Druid's Deliverance",'Doubling Season'])
        source=self.token(sim,'old squirrel',power=3,toughness=2,
                          colors=('Green',),subtypes=('Squirrel',),keywords=('reach',))
        source.counters=3;source.temporary_power=5;source.tapped=True
        self.put(sim,cards['Doubling Season'])
        sim.cast_spell(0,cards["Druid's Deliverance"])
        self.assertEqual(sum(item.card.is_token for item in sim.players[0].battlefield),1)
        self.drain(sim)
        tokens=[item for item in sim.players[0].battlefield if item.card.is_token]
        self.assertEqual(len(tokens),3)  # One original plus two from Doubling Season.
        for copy in (item for item in tokens if item is not source):
            self.assertEqual((copy.card.power,copy.card.toughness),(3,2))
            self.assertEqual(copy.counters,0)
            self.assertFalse(copy.tapped)
            self.assertEqual(copy.card.event_definition.subtypes,frozenset({'Squirrel'}))
            self.assertEqual(copy.card.event_definition.colors,frozenset({'Green'}))
            self.assertIn('reach',copy.card.event_definition.abilities)
        self.assertTrue(sim.combat_damage_prevented_to_players=={0})
        self.assertFalse(sim.combat_damage_prevented)
        sim.invariant()

    def test_prevent_player_combat_but_not_creature_combat_damage(self):
        sim,cards=self.fixture(["Druid's Deliverance"])
        sim.cast_spell(0,cards["Druid's Deliverance"]);self.drain(sim)
        self.assertEqual(sum(item.card.is_token for item in sim.players[0].battlefield),0)
        enemy=self.token(sim,'enemy attacker',seat=1,power=4,toughness=4)
        sim.active=1;sim.phase='attack';sim.stack.priority=1
        sim.declare_attackers([enemy.card.id]);sim.declare_blockers({})
        self.damage(sim)
        self.assertEqual(sim.players[0].life,40)
        blocker=self.token(sim,'own blocker',power=1,toughness=1)
        enemy2=self.token(sim,'second attacker',seat=1,power=3,toughness=3)
        sim.phase='attack';sim.stack.priority=1
        sim.declare_attackers([enemy2.card.id]);sim.declare_blockers({enemy2.card.id:[blocker.card.id]})
        self.damage(sim)
        self.assertNotIn(blocker,sim.players[0].battlefield)
        self.assertEqual(sim.players[0].life,40)
        sim.invariant()

    def test_prevention_expires_at_cleanup_without_removing_copies(self):
        sim,cards=self.fixture(["Druid's Deliverance"])
        self.token(sim,'token',subtypes=('Squirrel',))
        sim.cast_spell(0,cards["Druid's Deliverance"]);self.drain(sim)
        self.assertEqual(sum(item.card.is_token for item in sim.players[0].battlefield),2)
        sim.phase='cleanup';sim.step()
        self.assertFalse(sim.combat_damage_prevented_to_players)
        self.assertEqual(sum(item.card.is_token for item in sim.players[0].battlefield),2)
        sim.invariant()


if __name__=='__main__':unittest.main()
