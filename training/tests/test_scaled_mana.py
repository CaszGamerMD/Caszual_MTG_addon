"""Tap for a chosen color of mana scaled by currently controlled permanents."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s
import mana_pool

class ScaledManaChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Sanctum Weaver']
        source=s.import_diagnostic_card(self.rules,raw,0,'weaver',{'Green'})
        self.assertEqual(source.kind,'creature')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(source)
        permanent=self.put(sim,source)
        return sim,source,permanent

    def add_enchantment(self,sim,identifier,seat=0):
        d=s.EventDefinition(identifier,frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset())
        c=s.Card(identifier,identifier,'enchantment',event_definition=d,is_token=True)
        sim.enter_creature(c,sim.players[seat])
        return c

    def test_unseen_name_parameters_and_unknown_clause(self):
        raw=dict(self.lookup['Sanctum Weaver'],name='Unnamed mana gardener')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Green'}).kind,'creature')
        raw['oracleText']+='\nCreate a mysterious treasure.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Green'}).kind,'unsupported')
        raw['oracleText']='{T}: Add X mana of any one color, where X is the number of artifacts you control.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Green'}).kind,'creature')

    def test_summoning_sickness_color_choice_and_tapping(self):
        sim,card,source=self.prepare()
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,card.id,4)
        source.fresh=False
        self.add_enchantment(sim,'own')
        self.add_enchantment(sim,'enemy',1)
        self.assertEqual(len(sim.scaled_mana_choices(0)),5)
        sim.activate_scaled_mana(0,card.id,4)
        self.assertEqual(sim.players[0].mana_pool[4],2)
        self.assertTrue(source.tapped)
        with self.assertRaises(ValueError):sim.activate_scaled_mana(0,card.id,4)
        sim.invariant()

    def test_mana_payment_sees_dynamic_count_and_one_color_only(self):
        sim,card,source=self.prepare()
        source.fresh=False
        self.add_enchantment(sim,'own')
        self.add_enchantment(sim,'own2')
        options=dict(sim.mana_sources(0))[card.id]
        self.assertEqual(options[4][4],3)
        self.assertEqual(options[0][0],3)
        self.assertTrue(mana_pool.plan('{G}{G}{G}',mana_pool.ZERO,[(card.id,options)])['paid'])
        self.assertFalse(mana_pool.plan('{G}{W}',mana_pool.ZERO,[(card.id,options)])['paid'])
        self.add_enchantment(sim,'enemy',1)
        self.assertEqual(dict(sim.mana_sources(0))[card.id][4][4],3)
        sim.invariant()
