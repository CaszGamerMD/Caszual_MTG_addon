"""Creature-type entry choices discount only matching creature spells while source remains."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures
from oracle_abilities import compile_abilities

class ChosenCostReductionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)

    def test_real_unseen_parameter_and_unknown_clause(self):
        raw=dict(self.lookup["Urza's Incubator"])
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'real',{'Green'}).event_definition.cost_reductions,
                         ((('chosen_creature_type',),2),))
        raw['name']='Unseen Tribal Cost Reducer'
        raw['oracleText']=raw['oracleText'].replace('{2} less','{3} less')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'new',{'Green'}).event_definition.cost_reductions,
                         ((('chosen_creature_type',),3),))
        raw['oracleText']+='\nDraw a forbidden card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Creature spells of the chosen type cost {2} less to cast.'))
        self.assertIsNone(compile_abilities('As this artifact enters, choose a creature type.'))

    def test_controller_subtype_and_generic_cost_only(self):
        raw=self.lookup["Urza's Incubator"]
        source=s.import_diagnostic_card(self.rules,raw,0,'incubator',{'Green'})
        def spell(name,subtype,types=('Creature',),cost='{3}'):
            return s.import_diagnostic_card(self.rules,dict(name=name,types=list(types),subTypes=[subtype],
                superTypes=[],manaCost=cost,colors=['Green'],colorIdentity=['Green'],power='2',toughness='2',
                oracleText='Flying',quantity=1,layout='normal',faces=[]),0,name,{'Green'})
        human=spell('Human recruit','Human')
        goblin=spell('Goblin recruit','Goblin')
        colored=spell('Colored recruit','Human',cost='{3}{G}')
        other=spell('Human artifact','Human',types=('Artifact',),cost='{3}')
        sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[source,human,goblin,colored,other],s.demo_deck(1)),diagnostic=True)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        (p.hand if source in p.hand else p.library).remove(source)
        sim.enter_creature(source,p)
        permanent=next(x for x in p.battlefield if x.card.id==source.id)
        self.assertEqual(permanent.chosen_subtype,'Human')
        p.mana_pool=[0,0,0,0,0,1]
        self.assertTrue(sim.payment(human,seat=0)['paid'])
        self.assertFalse(sim.payment(goblin,seat=0)['paid'])
        self.assertFalse(sim.payment(other,seat=0)['paid'])
        self.assertFalse(sim.payment(colored,seat=0)['paid'])
        p.mana_pool=[0,0,0,0,1,1]
        self.assertTrue(sim.payment(colored,seat=0)['paid'])
        sim.players[1].mana_pool=[0,0,0,0,0,1]
        self.assertFalse(sim.payment(human,seat=1)['paid'])
        sim.send_to_destination(p,permanent)
        self.assertFalse(sim.payment(human,seat=0)['paid'])
        sim.invariant()
