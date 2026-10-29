"""Composed land mana and paid tap-to-counter-every-controlled-creature abilities."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class LandTeamCounterChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Gavony Township']
        land=s.import_diagnostic_card(self.rules,raw,0,'township',{'Green','White'})
        self.assertEqual(land.kind,'land')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(land)
        source=self.put(sim,land)
        return sim,land,source

    def test_full_text_unseen_name_cost_variants_and_unknown_clause(self):
        raw=dict(self.lookup['Gavony Township'],name='Unknown borough')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Green','White'}).kind,'land')
        raw['oracleText']='{T}: Add {C}.\n{1}{R}, {T}: Put a +1/+1 counter on each creature you control.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Red'}).kind,'land')
        raw['oracleText']+='\nDraw an unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Red'}).kind,'unsupported')

    def test_land_cannot_pay_own_tap_cost_and_ability_uses_stack(self):
        sim,land,source=self.prepare()
        ally=self.token(sim,'ally')
        enemy=self.token(sim,'enemy',seat=1)
        self.assertTrue(any(c.kind=='activate_land_counters' for c in sim.land_counter_choices(0)))
        sim.activate_land_counters(0,land.id)
        self.assertTrue(source.tapped)
        self.assertEqual(ally.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        with self.assertRaises(ValueError):sim.activate_land_counters(0,land.id)
        self.drain(sim)
        self.assertEqual(ally.counters,1)
        self.assertEqual(enemy.counters,0)
        sim.invariant()

    def test_resolution_uses_current_control_and_counter_replacement(self):
        sim,land,source=self.prepare()
        early=self.token(sim,'early')
        sim.activate_land_counters(0,land.id)
        late=self.token(sim,'late')
        sim.players[0].battlefield.remove(early)
        sim.players[1].battlefield.append(early)
        self.drain(sim)
        self.assertEqual(early.counters,0)
        self.assertEqual(late.counters,1)
        sim.invariant()

    def test_tap_cost_requires_other_sources_or_floating_mana(self):
        sim,land,source=self.prepare()
        for p in sim.players[0].battlefield:
            if p.card.id!=land.id and p.card.kind=='land':p.tapped=True
        self.assertFalse(sim.land_counter_choices(0))
        with self.assertRaises(ValueError):sim.activate_land_counters(0,land.id)
        sim.players[0].mana_pool=[1,0,0,0,1,2]
        self.assertTrue(sim.land_counter_choices(0))
        sim.activate_land_counters(0,land.id)
        self.assertEqual(sim.players[0].mana_pool,[0]*6)
        self.drain(sim)
        sim.invariant()
