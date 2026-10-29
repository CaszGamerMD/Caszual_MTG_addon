"""Discard-cost token activation and its composition with attack-group draw."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SessionLearningDiscardTokens(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_real_alliance_unseen_name_variant_and_unknown_remainder(self):
        raw=dict(self.lookup['Chivalric Alliance'])
        card=s.import_diagnostic_card(self.rules,raw,0,'real',{'White'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual(card.event_definition.attack_group_draw,(2,1))
        self.assertEqual(card.event_definition.discard_token_ability[0],'{2}')
        self.assertEqual(card.event_definition.discard_token_ability[1].subtypes,('Knight',))
        raw['name']='Unseen card-for-token guild'
        raw['oracleText']=raw['oracleText'].replace('{2}, Discard','{3}, Discard').replace('2/2 white and blue Knight','3/3 black Rogue')
        altered=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertNotEqual(altered.kind,'unsupported')
        self.assertEqual(altered.event_definition.discard_token_ability[1].power,3)
        raw['oracleText']+='\nDo something not supported.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_discard_is_paid_before_stack_resolution_and_creates_token(self):
        sim,cards=self.fixture(['Chivalric Alliance'])
        source=self.put(sim,cards['Chivalric Alliance'])
        player=sim.players[0]
        if not player.hand:player.hand.append(player.library.pop())
        discard=player.hand[0]
        before=len(player.hand)
        sim.activate_discard_tokens(0,source.card.id,discard.id)
        self.assertEqual(len(player.hand),before-1)
        self.assertIn(discard,player.graveyard)
        self.assertFalse(any(p.card.is_token for p in player.battlefield))
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        knights=[p for p in player.battlefield if p.card.is_token]
        self.assertEqual(len(knights),1)
        self.assertEqual(knights[0].card.event_definition.subtypes,frozenset({'Knight'}))
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[knights[0].card.id],'vigilance'))
        sim.invariant()

    def test_unpaid_mana_or_missing_card_cannot_discard(self):
        sim,cards=self.fixture(['Chivalric Alliance'])
        source=self.put(sim,cards['Chivalric Alliance'])
        player=sim.players[0]
        if not player.hand:player.hand.append(player.library.pop())
        before=list(player.hand)
        with self.assertRaises(ValueError):sim.activate_discard_tokens(0,source.card.id,'not-in-hand')
        for land in player.battlefield:
            if land.card.kind=='land':land.tapped=True
        with self.assertRaises(ValueError):sim.activate_discard_tokens(0,source.card.id,before[0].id)
        self.assertEqual(player.hand,before)
        sim.invariant()

    def test_same_permanent_draws_on_two_declared_attackers(self):
        sim,cards=self.fixture(['Chivalric Alliance'])
        self.put(sim,cards['Chivalric Alliance'])
        a=self.token(sim,'one');b=self.token(sim,'two')
        self.ready(sim)
        before=len(sim.players[0].hand)
        sim.declare_attackers([a.card.id,b.card.id])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(len(sim.players[0].hand),before+1)
        sim.invariant()
