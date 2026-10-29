"""Subtype sacrifice costs for mana abilities, including real zone events."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SacrificeManaChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Skirk Prospector']
        card=s.import_diagnostic_card(self.rules,raw,0,'prospector',{'Red'})
        self.assertEqual(card.kind,'creature')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(card)
        source=self.put(sim,card)
        return sim,card,source

    def test_real_unseen_subtype_and_unknown_text(self):
        raw=dict(self.lookup['Skirk Prospector'],name='Unfamiliar miner')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Red'}).kind,'creature')
        raw['oracleText']='Sacrifice an Elf: Add {G}.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Green'}).kind,'creature')
        raw['oracleText']+='\nDraw an unknown card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Green'}).kind,'unsupported')

    def test_sacrifice_token_cost_adds_mana_not_stack_and_restricts_subtype(self):
        sim,card,source=self.prepare()
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        options=sim.sacrifice_choices(0)
        self.assertIn('goblin',{c.tap_ids[0] for c in options})
        self.assertNotIn('elf',{c.tap_ids[0] for c in options})
        self.assertNotIn('enemy',{c.tap_ids[0] for c in options})
        with self.assertRaises(ValueError):sim.activate_sacrifice_mana(0,card.id,'elf')
        with self.assertRaises(ValueError):sim.activate_sacrifice_mana(0,card.id,'enemy')
        sim.activate_sacrifice_mana(0,card.id,'goblin')
        self.assertEqual(sim.players[0].mana_pool[3],1)
        self.assertNotIn(goblin,sim.players[0].battlefield)
        self.assertFalse(sim.stack.items)
        self.assertIn(elf,sim.players[0].battlefield)
        sim.invariant()

    def test_sacrifice_non_token_source_and_no_summoning_sickness_requirement(self):
        sim,card,source=self.prepare()
        self.assertTrue(source.fresh)
        sim.activate_sacrifice_mana(0,card.id,card.id)
        self.assertEqual(sim.players[0].mana_pool[3],1)
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertIn(card,sim.players[0].graveyard)
        with self.assertRaises(ValueError):sim.activate_sacrifice_mana(0,card.id,card.id)
        sim.invariant()

    def test_mana_can_pay_generic_and_red_after_sacrifice(self):
        sim,card,_=self.prepare()
        self.token(sim,'goblin',subtypes=('Goblin',))
        sim.activate_sacrifice_mana(0,card.id,'goblin')
        self.assertTrue(s.mana_pool.plan('{R}',sim.players[0].mana_pool,[])['paid'])
        self.assertTrue(s.mana_pool.plan('{1}',sim.players[0].mana_pool,[])['paid'])
        self.assertFalse(s.mana_pool.plan('{G}',sim.players[0].mana_pool,[])['paid'])
        sim.invariant()
