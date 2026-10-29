"""End-step buffed-creature intervening-if condition checks twice."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as h
class BuffedEndStepTests(unittest.TestCase):
    setUpClass=classmethod(h.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(h.EnchantmentChecks.tearDownClass.__func__)
    fixture=h.EnchantmentChecks.fixture
    put=h.EnchantmentChecks.put
    token=h.EnchantmentChecks.token
    drain=h.EnchantmentChecks.drain
    def test_unseen_parameters_and_extra_clause(self):
        raw=dict(self.lookup['Baird, Argivian Recruiter'],name='Unseen endstep captain')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',set())
        self.assertEqual(card.kind,'creature')
        self.assertTrue(card.event_definition.triggers[0].power_above_base_required)
        raw['oracleText']=raw['oracleText'].replace('a 1/1 white Soldier','two 2/2 green Elf')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'variant',set()).kind,'creature')
        raw['oracleText']+='\nDo something unknown.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
    def test_trigger_condition_and_resolution_recheck(self):
        sim,cards=self.fixture(['Baird, Argivian Recruiter'])
        source=self.put(sim,cards['Baird, Argivian Recruiter'])
        ally=self.token(sim,'ally')
        self.assertFalse(sim.event_game('end_step').end_step_triggers(0))
        ally.counters=1
        events=sim.event_game('end_step').end_step_triggers(0)
        self.assertEqual(len(events),1)
        sim.resolve_entry_triggers(events,source.card)
        ally.counters=0
        self.drain(sim)
        self.assertFalse(any(p.card.name=='Soldier' for p in sim.players[0].battlefield))
        ally.counters=1
        sim.resolve_entry_triggers(sim.event_game('end_step').end_step_triggers(0),source.card)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(sum(p.card.name=='Soldier' for p in sim.players[0].battlefield),1)
        sim.invariant()
