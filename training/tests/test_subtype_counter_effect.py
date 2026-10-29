import unittest
import test_enchantment_abilities as fixtures
import simulator as s
from oracle_abilities import compile_abilities

class SubtypeCounterChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_unseen_subtypes_and_unknown_remainder(self):
        for subtype in ('Villain','Goblin','Faerie','Squirrel'):
            text=f'Whenever you gain life, put two +1/+1 counters on each {subtype} you control.'
            # Numeric Oracle forms supported by the existing counter grammar.
            text=text.replace('two','2')
            p=compile_abilities(text,'Unseen observer')
            self.assertEqual(p.triggers[0].effect.counter_subtype,subtype)
            self.assertEqual(p.triggers[0].effect.amount,2)
            self.assertIsNone(compile_abilities(text+'\nDo an unknown thing.'))
        raw=dict(self.lookup['Citizen V, Helmut Zemo'],name='Unseen observer')
        self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,'new',set()).kind,'unsupported')

    def test_live_subtype_filter_controller_and_replacement(self):
        sim,cards=self.fixture(['Citizen V, Helmut Zemo','Hardened Scales'])
        source=self.put(sim,cards['Citizen V, Helmut Zemo'])
        self.put(sim,cards['Hardened Scales'])
        other=self.token(sim,'other',subtypes=('Goblin',))
        enemy=self.token(sim,'enemy',1,subtypes=('Villain',))
        sim.gain_life(0,7)
        sim.resolve_entry_triggers([],source.card)
        self.assertEqual(source.counters,0)
        late=self.token(sim,'late',subtypes=('Villain',))
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(late.counters,2)
        self.assertEqual(other.counters,0);self.assertEqual(enemy.counters,0)
        sim.invariant()
