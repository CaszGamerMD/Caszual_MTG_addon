"""Generic tapped token ability counts matching permanents at resolution."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class TribalTapTokenChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Krenko, Mob Boss']
        source=s.import_diagnostic_card(self.rules,raw,0,'krenko',{'Red'})
        self.assertEqual(source.kind,'creature')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(source)
        permanent=self.put(sim,source)
        return sim,source,permanent

    def test_unseen_names_and_unknown_clause_rejected(self):
        raw=dict(self.lookup['Krenko, Mob Boss'],name='Unfamiliar captain')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Red'}).kind,'creature')
        raw['oracleText']+='\nDraw a card without paying.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Red'}).kind,'unsupported')
        raw['oracleText']='{T}: Create X 2/2 green Elf creature tokens, where X is the number of Elves you control.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Red'}).kind,'creature')

    def test_tap_and_summoning_sickness_and_reactivation(self):
        sim,card,source=self.prepare()
        self.assertFalse(any(c.kind=='activate_tribal_tokens' for c in sim.token_ability_choices(0)))
        with self.assertRaises(ValueError):sim.activate_tribal_tokens(0,card.id)
        source.fresh=False
        self.assertTrue(any(c.kind=='activate_tribal_tokens' for c in sim.token_ability_choices(0)))
        sim.activate_tribal_tokens(0,card.id)
        self.assertTrue(source.tapped)
        with self.assertRaises(ValueError):sim.activate_tribal_tokens(0,card.id)
        self.drain(sim)
        goblins=[p for p in sim.players[0].battlefield if p.card.is_token and 'Goblin' in p.card.event_definition.subtypes]
        self.assertEqual(len(goblins),1)
        sim.invariant()

    def test_count_at_resolution_not_activation_and_count_only_own(self):
        sim,card,source=self.prepare()
        source.fresh=False
        self.token(sim,'ally-goblin',subtypes=('Goblin',))
        self.token(sim,'enemy-goblin',seat=1,subtypes=('Goblin',))
        sim.activate_tribal_tokens(0,card.id)
        self.token(sim,'late-goblin',subtypes=('Goblin',))
        self.drain(sim)
        created=[p for p in sim.players[0].battlefield if p.card.is_token and p.card.id.startswith('token-')]
        self.assertEqual(len(created),3)
        sim.invariant()
