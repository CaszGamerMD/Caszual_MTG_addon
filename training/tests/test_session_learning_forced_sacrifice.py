"""Sigarda-style opposing sacrifice prevention, with a real edict resolution."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

NAME='Sigarda, Host of Herons'

class SessionLearningForcedSacrifice(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def edict(self,name='Unseen mandatory edict',text='Each opponent sacrifices a creature.'):
        return dict(name=name,types=['Sorcery'],subTypes=[],superTypes=[],
                    colors=['Black'],colorIdentity=['Black'],manaCost='{1}{B}',
                    quantity=1,layout='normal',oracleText=text)

    def test_real_unseen_prevention_and_malformed_remainder(self):
        card=s.import_diagnostic_card(self.rules,self.lookup[NAME],0,'sigarda',{'Green','White'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertTrue(card.event_definition.prevents_opponent_sacrifice)
        raw=dict(self.lookup[NAME],name='Unfamiliar angel guardian')
        raw['oracleText']=raw['oracleText'].replace('Flying, hexproof','Reach, hexproof')
        variant=s.import_diagnostic_card(self.rules,raw,0,'variant',{'Green','White'})
        self.assertNotEqual(variant.kind,'unsupported')
        self.assertIn('reach',variant.event_definition.abilities)
        raw['oracleText']+='\nDo something mysterious.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green','White'}).kind,'unsupported')

    def test_edict_parser_variations_and_unsupported_clause(self):
        for name in ('Unseen mandatory edict','Another fresh sacrifice effect'):
            card=s.import_diagnostic_card(self.rules,self.edict(name=name),0,'edict',{'Black'})
            self.assertEqual(card.kind,'sacrifice_spell')
            self.assertEqual(card.forced_sacrifice,('opponent',1))
        for extra in ('Each player sacrifices two creatures.',
                      'Each opponent sacrifices two creatures.',
                      'Each opponent sacrifices a creature.\nDraw an unknown thing.'):
            self.assertEqual(s.import_diagnostic_card(
                self.rules,self.edict(text=extra),0,'bad',{'Black'}).kind,'unsupported')

    def test_opponent_edict_is_prevented_during_spell_resolution(self):
        raw=self.edict()
        self.lookup[raw['name']]=raw
        sim,cards=self.fixture([NAME,raw['name']])
        angel=cards[NAME]
        sim.players[0].hand.remove(angel)
        source=sim.enter_creature(angel,sim.players[1])
        angel_permanent=next(p for p in sim.players[1].battlefield if p.card.id==angel.id)
        victim=self.token(sim,'enemy-token',seat=1,power=1,toughness=1)
        sim.cast_spell(0,cards[raw['name']])
        self.assertIn(victim,sim.players[1].battlefield)
        self.drain(sim)
        self.assertIn(victim,sim.players[1].battlefield)
        self.assertTrue(any(e['kind']=='sacrifice_prevented' for e in sim.events))
        sim.send_to_destination(sim.players[1],angel_permanent)
        self.assertTrue(sim.force_opponent_sacrifice(0,1,cards[raw['name']]))
        self.assertNotIn(victim,sim.players[1].battlefield)
        sim.invariant()

    def test_self_controlled_edict_and_sacrifice_costs_not_prevented(self):
        sim,cards=self.fixture([NAME])
        angel=self.put(sim,cards[NAME])
        victim=self.token(sim,'own-token',power=1,toughness=1)
        self.assertTrue(sim.force_opponent_sacrifice(0,0,angel.card))
        self.assertNotIn(victim,sim.players[0].battlefield)
        next_victim=self.token(sim,'another-token')
        sim._pay_sacrifice_creature(0,next_victim)
        self.assertNotIn(next_victim,sim.players[0].battlefield)
        self.assertIn(angel,sim.players[0].battlefield)
        sim.invariant()
