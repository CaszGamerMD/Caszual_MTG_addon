"""Subtype sacrifice cost and targeted temporary creature boosts."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class SacrificeBoostChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def prepare(self):
        sim,cards=self.fixture(['Lifelink'])
        raw=self.lookup['Goblin Sledder']
        card=s.import_diagnostic_card(self.rules,raw,0,'sledder',{'Red'})
        self.assertEqual(card.kind,'creature')
        sim.players[0].hand.remove(cards['Lifelink'])
        sim.players[0].hand.append(card)
        source=self.put(sim,card)
        return sim,card,source

    def test_complete_oracle_unseen_name_parameters_and_unknown_text(self):
        raw=dict(self.lookup['Goblin Sledder'],name='Unnamed goblin feeder')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Red'}).kind,'creature')
        raw['oracleText']='Sacrifice an Elf: Target creature gets +2/+3 until end of turn.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Red'}).kind,'creature')
        raw['oracleText']+='\nGain an unknown bonus.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Red'}).kind,'unsupported')

    def test_cost_paid_before_stack_and_boost_after_resolution(self):
        sim,card,source=self.prepare()
        victim=self.token(sim,'goblin',subtypes=('Goblin',))
        target=self.token(sim,'target',power=3,toughness=4)
        sim.activate_sacrifice_boost(0,card.id,'goblin','target')
        self.assertNotIn(victim,sim.players[0].battlefield)
        self.assertEqual(sim.effective_card(target).power,3)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual((sim.effective_card(target).power,sim.effective_card(target).toughness),(4,5))
        self.assertEqual(sim.players[0].mana_pool[3],0)
        sim.invariant()

    def test_fizzle_after_target_leaves_and_source_may_be_sacrificed(self):
        sim,card,source=self.prepare()
        target=self.token(sim,'target')
        sim.activate_sacrifice_boost(0,card.id,card.id,'target')
        self.assertNotIn(source,sim.players[0].battlefield)
        sim.send_to_destination(sim.players[0],target)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='sacrifice_boost_fizzle' for e in sim.events))
        sim.invariant()

    def test_illegal_target_and_sacrifice_are_rejected_before_cost(self):
        sim,card,source=self.prepare()
        elf=self.token(sim,'elf',subtypes=('Elf',))
        shrouded=self.token(sim,'hidden',keywords=('shroud',))
        protected=self.token(sim,'protected',seat=1,keywords=('protection from red',))
        with self.assertRaises(ValueError):sim.activate_sacrifice_boost(0,card.id,'elf',card.id)
        with self.assertRaises(ValueError):sim.activate_sacrifice_boost(0,card.id,card.id,shrouded.card.id)
        with self.assertRaises(ValueError):sim.activate_sacrifice_boost(0,card.id,card.id,protected.card.id)
        self.assertIn(source,sim.players[0].battlefield)
        sim.invariant()
