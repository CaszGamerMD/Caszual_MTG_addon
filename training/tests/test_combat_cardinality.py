"""Parameterized attacking and blocking cardinality restrictions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f
class CombatCardinalityChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    token=f.EnchantmentChecks.token
    ready=f.EnchantmentChecks.ready
    drain=f.EnchantmentChecks.drain
    def test_real_unseen_numbers_and_unknown_remainder(self):
        raw=dict(self.lookup['Mirri, Weatherlight Duelist'],name='Unknown Duelist')
        raw['oracleText']=raw['oracleText'].replace('Mirri','Unknown Duelist')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'u',set()).event_definition.combat_limits,(1,1))
        other=dict(raw,oracleText=raw['oracleText'].replace('one creature','two creatures'))
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'v',set()).event_definition.combat_limits,(2,2))
        self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,oracleText=raw['oracleText']+'\nDraw three cards.'),0,'bad',set()).kind,'unsupported')
    def test_trigger_uses_stack_and_limits_blockers(self):
        sim,cards=self.fixture(['Mirri, Weatherlight Duelist'])
        mirri=self.put(sim,cards['Mirri, Weatherlight Duelist'])
        other=self.token(sim,'other-attacker')
        b1=self.token(sim,'blocker1',seat=1);b2=self.token(sim,'blocker2',seat=1)
        self.ready(sim);sim.declare_attackers([mirri.card.id,other.card.id])
        self.assertIsNone(sim.group_combat['block_limit'])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertEqual(sim.group_combat['block_limit'],1)
        with self.assertRaisesRegex(ValueError,'Too many blockers'):
            sim.declare_blockers({mirri.card.id:(b1.card.id,),other.card.id:(b2.card.id,)})
        sim.declare_blockers({other.card.id:(b2.card.id,)})
        sim.invariant()
    def test_trigger_survives_source_departure(self):
        sim,cards=self.fixture(['Mirri, Weatherlight Duelist'])
        mirri=self.put(sim,cards['Mirri, Weatherlight Duelist'])
        self.ready(sim);sim.declare_attackers([mirri.card.id])
        sim.send_to_destination(sim.players[0],mirri);self.drain(sim)
        self.assertEqual(sim.group_combat['block_limit'],1)
        sim.invariant()
    def test_tapped_defender_limits_attackers(self):
        sim,cards=self.fixture(['Mirri, Weatherlight Duelist'])
        mirri=self.put(sim,cards['Mirri, Weatherlight Duelist'])
        a=self.token(sim,'a',seat=1);b=self.token(sim,'b',seat=1)
        sim.active=1;sim.phase='attack';sim.stack.priority=1;mirri.tapped=True
        with self.assertRaisesRegex(ValueError,'Too many attackers'):
            sim.declare_attackers([a.card.id,b.card.id])
        self.assertTrue(all(len(x.attack_ids)<=1 for x in sim.group_attack_choices(1) if x.kind=='attack_group'))
        mirri.tapped=False;sim.declare_attackers([a.card.id,b.card.id])
        self.assertEqual(len(sim.group_combat['attackers']),2)
        sim.invariant()
