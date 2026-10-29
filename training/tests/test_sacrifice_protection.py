"""Sacrifice as cost, target revalidation, and temporary chosen-color protection."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SacrificeProtectionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_full_oracle_unseen_name_cost_variant_and_reject_unknown(self):
        raw=dict(self.lookup["Alseid of Life's Bounty"],name='Unseen warding nymph')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'White'}).kind,'creature')
        raw['oracleText']=raw['oracleText'].replace('{1}, Sacrifice','{2}{W}, Sacrifice')
        variant=s.import_diagnostic_card(self.rules,raw,0,'b',{'White'})
        self.assertEqual(variant.event_definition.sacrifice_protection[0],'{2}{W}')
        raw['oracleText']+='\nDraw an unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_sacrifice_cost_then_protection_resolves_and_expires(self):
        sim,cards=self.fixture(["Alseid of Life's Bounty"])
        source=self.put(sim,cards["Alseid of Life's Bounty"])
        ally=self.token(sim,'ally',power=2,toughness=2)
        sim.activate_sacrifice_protection(0,source.card.id,ally.card.id,'Red')
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertFalse(sim.event_game('main').has(sim.event_game('main').battlefield[ally.card.id],'protection from red'))
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[ally.card.id],'protection from red'))
        self.assertTrue(game.protected(game.battlefield[ally.card.id],{'Red'}))
        game.cleanup();sim.sync_events(game)
        self.assertFalse(sim.event_game('main').has(sim.event_game('main').battlefield[ally.card.id],'protection from red'))
        sim.invariant()

    def test_target_becomes_illegal_after_sacrifice_cost(self):
        sim,cards=self.fixture(["Alseid of Life's Bounty"])
        source=self.put(sim,cards["Alseid of Life's Bounty"])
        ally=self.token(sim,'ally')
        sim.activate_sacrifice_protection(0,source.card.id,ally.card.id,'Blue')
        ally.temporary_abilities=frozenset({'shroud'})
        self.drain(sim)
        self.assertTrue(any(e['kind']=='sacrifice_protection_fizzle' for e in sim.events))
        self.assertFalse(sim.event_game('main').has(sim.event_game('main').battlefield[ally.card.id],'protection from blue'))
        sim.invariant()

    def test_invalid_target_or_unpaid_cost_does_not_sacrifice(self):
        sim,cards=self.fixture(["Alseid of Life's Bounty"])
        source=self.put(sim,cards["Alseid of Life's Bounty"])
        enemy=self.token(sim,'enemy',seat=1)
        with self.assertRaises(ValueError):sim.activate_sacrifice_protection(0,source.card.id,enemy.card.id,'Red')
        for permanent in sim.players[0].battlefield:
            if permanent.card.kind=='land':permanent.tapped=True
        with self.assertRaises(ValueError):sim.activate_sacrifice_protection(0,source.card.id,source.card.id,'Red')
        self.assertIn(source,sim.players[0].battlefield)
        sim.invariant()
