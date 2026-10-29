"""Umbra armor: destruction replacement, not regeneration or sacrifice prevention."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SessionLearningUmbraArmor(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Hyena Umbra'])
        host=self.token(sim,'umbra-host',power=2,toughness=2)
        aura=self.put(sim,cards['Hyena Umbra'],target=host.card.id)
        return sim,host,aura

    def test_actual_umbra_and_unseen_variants_fail_closed(self):
        raw=dict(self.lookup['Hyena Umbra'])
        parsed=s.import_diagnostic_card(self.rules,raw,0,'real',{'White'})
        self.assertNotEqual(parsed.kind,'unsupported')
        self.assertTrue(parsed.event_definition.umbra_armor)
        raw['name']='Unseen protective aura'
        raw['oracleText']=raw['oracleText'].replace('+1/+1','+2/+2')
        variant=s.import_diagnostic_card(self.rules,raw,0,'variant',{'White'})
        self.assertNotEqual(variant.kind,'unsupported')
        raw['oracleText']+='\nDraw an unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_explicit_destroy_consumes_aura_not_creature(self):
        sim,host,aura=self.prepare()
        host.marked_damage=1
        sim.destroy_batch(((0,host),),host.card)
        self.assertIn(host,sim.players[0].battlefield)
        self.assertNotIn(aura,sim.players[0].battlefield)
        self.assertIn(aura.card,sim.players[0].graveyard)
        self.assertEqual(host.marked_damage,0)
        self.assertFalse(host.tapped)
        sim.invariant()

    def test_lethal_damage_replaces_destruction_and_clears_damage(self):
        sim,host,aura=self.prepare()
        host.marked_damage=5
        sim.resolve_entry_triggers(sim.state_based_actions(),host.card)
        self.assertIn(host,sim.players[0].battlefield)
        self.assertNotIn(aura,sim.players[0].battlefield)
        self.assertEqual(host.marked_damage,0)
        sim.invariant()

    def test_sacrifice_and_zero_toughness_are_not_replaced(self):
        sim,host,aura=self.prepare()
        sim._pay_sacrifice_creature(0,host)
        sim.state_based_actions()
        self.assertNotIn(host,sim.players[0].battlefield)
        self.assertNotIn(aura,sim.players[0].battlefield)
        sim.invariant()
        sim,host,aura=self.prepare()
        host.temporary_toughness=-3
        sim.state_based_actions()
        self.assertNotIn(host,sim.players[0].battlefield)
        self.assertNotIn(aura,sim.players[0].battlefield)
        sim.invariant()
