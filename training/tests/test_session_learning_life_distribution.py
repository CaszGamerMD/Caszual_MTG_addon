"""End-step gained-life counters: trigger-time allocation, real targets, LKI and replacements."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class SessionLearningLifeDistribution(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def setup_game(self):
        sim,cards=self.fixture(['Lathiel, the Bounteous Dawn'])
        unicorn=self.put(sim,cards['Lathiel, the Bounteous Dawn'])
        host=self.token(sim,'first-bonus',power=2,toughness=3)
        return sim,unicorn,host

    def test_real_and_unseen_variants_and_reject_extra_clause(self):
        raw=dict(self.lookup['Lathiel, the Bounteous Dawn'])
        actual=s.import_diagnostic_card(self.rules,raw,0,'real',{'White','Green'})
        self.assertNotEqual(actual.kind,'unsupported')
        self.assertTrue(actual.event_definition.end_step_life_distribution)
        raw['name']='Unseen life-gain tactician'
        raw['oracleText']=raw['oracleText'].replace('Lifelink','Vigilance, lifelink')
        changed=s.import_diagnostic_card(self.rules,raw,0,'renamed',{'White','Green'})
        self.assertNotEqual(changed.kind,'unsupported')
        self.assertIn('vigilance',changed.event_definition.abilities)
        raw['oracleText']+='\nDo something unknown.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'White','Green'}).kind,'unsupported')

    def test_gaining_life_stacks_trigger_and_source_can_leave(self):
        sim,unicorn,host=self.setup_game()
        sim.gain_life(0,3)
        sim.phase='end_step'
        sim.step()
        self.assertEqual(host.counters,0)
        self.assertEqual(len(sim.stack.items),1)
        event=sim.stack.items[-1].payload[0]
        self.assertEqual(event['distribution'],{host.card.id:3})
        sim.gain_life(0,5)
        sim.send_to_destination(sim.players[0],unicorn)
        self.drain(sim)
        self.assertEqual(host.counters,3)
        sim.invariant()

    def test_partial_illegal_targets_keep_original_allocation(self):
        sim,unicorn,a=self.setup_game()
        b=self.token(sim,'second-bonus',power=1,toughness=1)
        sim.choose_life_counter_distribution=lambda e,targets:{a.card.id:2,b.card.id:1}
        sim.gain_life(0,3)
        sim.phase='end_step'
        sim.step()
        sim.send_to_destination(sim.players[0],b)
        self.drain(sim)
        self.assertEqual(a.counters,2)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.id==b.card.id]),0)
        sim.invariant()

    def test_opponent_end_step_also_checks_my_life_gain(self):
        sim,cards=self.fixture(['Lathiel, the Bounteous Dawn'])
        unicorn=cards['Lathiel, the Bounteous Dawn']
        sim.players[0].hand.remove(unicorn)
        sim.enter_creature(unicorn,sim.players[1])
        host=self.token(sim,'opponent-step-bonus',seat=1)
        sim.gain_life(1,2)
        sim.phase='end_step'
        sim.step()
        self.assertEqual(sim.stack.items[-1].payload[0]['controller'],1)
        self.drain(sim)
        self.assertEqual(host.counters,2)
        sim.invariant()

    def test_zero_gain_and_bad_distributions(self):
        sim,_,host=self.setup_game()
        sim.phase='end_step'
        sim.step()
        self.assertFalse(sim.stack.items)
        sim.invariant()
        sim,source,host=self.setup_game()
        sim.gain_life(0,2)
        sim.choose_life_counter_distribution=lambda e,targets:{source.card.id:2}
        with self.assertRaises(ValueError):sim.queue_life_counter_triggers(sim.event_game('end_step'))
