"""Variable characteristic-defining P/T regression tests."""
import sys,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f
class ColoredPermanentPTChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    def test_unseen_colors_and_unknown_clause(self):
        raw=dict(self.lookup['Faerie Swarm'],name='Unknown Variable Creature')
        raw['oracleText']=raw['oracleText'].replace('Faerie Swarm',raw['name'])
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'u',set()).event_definition.dynamic_pt_color,'Blue')
        changed=dict(raw,oracleText=raw['oracleText'].replace('blue','green'))
        self.assertEqual(s.import_diagnostic_card(self.rules,changed,0,'v',set()).event_definition.dynamic_pt_color,'Green')
        self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,oracleText=raw['oracleText']+'\nDraw two cards.'),0,'bad',set()).kind,'unsupported')
        self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,power='2',toughness='2'),0,'bad2',set()).kind,'unsupported')
    def test_live_controller_count_and_modifiers(self):
        sim,cards=self.fixture(['Faerie Swarm'])
        swarm=self.put(sim,cards['Faerie Swarm'])
        self.assertEqual(sim.effective_card(swarm).power,1)
        d=s.EventDefinition('Blue source',frozenset({'Enchantment'}),frozenset(),False,0,0,frozenset(),colors=frozenset({'Blue'}))
        c=s.Card('blue-source','Blue source','enchantment',event_definition=d,is_token=True)
        sim.enter_creature(c,sim.players[0]);sim.enter_creature(replace(c,id='enemy'),sim.players[1])
        self.assertEqual((sim.effective_card(swarm).power,sim.effective_card(swarm).toughness),(2,2))
        swarm.counters=1;swarm.temporary_power=-1
        self.assertEqual((sim.effective_card(swarm).power,sim.effective_card(swarm).toughness),(2,3))
        own=next(p for p in sim.players[0].battlefield if p.card.id==c.id)
        sim.send_to_destination(sim.players[0],own)
        self.assertEqual(sim.effective_card(swarm).power,1)
        sim.invariant()
