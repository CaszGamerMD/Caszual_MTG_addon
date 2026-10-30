"""Nontoken death trigger optionally pays mana to return source to owner's hand."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class PaidReturnDeathChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    token=fixtures.EnchantmentChecks.token

    def kill(self,sim,item,seat=0):
        game=sim.event_game('main')
        pending=game.death_triggers([item.card.id])
        sim.send_to_destination(sim.players[seat],item,snapshot=game)
        sim.resolve_entry_triggers(pending,item.card)

    def actual(self):return dict(self.lookup['Squirrel Sanctuary'])

    def test_real_renamed_costs_and_unknown_text(self):
        raw=self.actual();raw['name']='Unseen Creature Refuge'
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertNotEqual(card.kind,'unsupported')
        self.assertEqual([t.effect.operation for t in card.event_definition.triggers],
                         ['create_tokens','pay_return_source'])
        raw['oracleText']=raw['oracleText'].replace('pay {1}','pay {3}')
        changed=s.import_diagnostic_card(self.rules,raw,0,'changed',{'Green'})
        self.assertEqual(changed.event_definition.triggers[1].effect.amount,3)
        raw['oracleText']+='\nWhen it returns, win the game.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        raw=self.actual();raw['types']=['Creature']
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'wrongtype',{'Green'}).kind,'unsupported')

    def test_entry_creates_token_and_nontoken_death_pays_then_returns(self):
        sim,cards=self.fixture(['Squirrel Sanctuary'])
        source=self.put(sim,cards['Squirrel Sanctuary'])
        self.drain(sim)
        self.assertTrue(any(p.card.is_token and p.card.name=='Squirrel' for p in sim.players[0].battlefield))
        creature=next(c for c in sim.players[0].library if c.kind=='creature')
        sim.players[0].library.remove(creature)
        sim.enter_creature(creature,sim.players[0])
        victim=next(p for p in sim.players[0].battlefield if p.card.id==creature.id)
        self.kill(sim,victim)
        self.assertTrue(any(f.payload[0]['operation']=='pay_return_source' for f in sim.stack.items))
        self.drain(sim)
        self.assertIn(source.card,sim.players[0].hand)
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertTrue(any(p.tapped for p in sim.players[0].battlefield if p.card.kind=='land'))
        sim.invariant()

    def test_token_death_does_not_trigger_and_optional_decline(self):
        sim,cards=self.fixture(['Squirrel Sanctuary'])
        self.put(sim,cards['Squirrel Sanctuary']);self.drain(sim)
        victim=next(p for p in sim.players[0].battlefield if p.card.is_token)
        self.kill(sim,victim)
        self.assertFalse(any(f.payload[0]['operation']=='pay_return_source' for f in sim.stack.items))
        sim.invariant()
        creature=next(c for c in sim.players[0].library if c.kind=='creature')
        sim.players[0].library.remove(creature)
        sim.enter_creature(creature,sim.players[0])
        victim=next(p for p in sim.players[0].battlefield if p.card.id==creature.id)
        self.kill(sim,victim)
        with patch.object(sim,'choose_optional_pay_return',return_value=False):self.drain(sim)
        self.assertTrue(any(p.card.name=='Squirrel Sanctuary' for p in sim.players[0].battlefield))
        sim.invariant()

    def test_source_leaves_before_trigger_resolves(self):
        sim,cards=self.fixture(['Squirrel Sanctuary'])
        source=self.put(sim,cards['Squirrel Sanctuary']);self.drain(sim)
        creature=next(c for c in sim.players[0].library if c.kind=='creature')
        sim.players[0].library.remove(creature);sim.enter_creature(creature,sim.players[0])
        victim=next(p for p in sim.players[0].battlefield if p.card.id==creature.id)
        self.kill(sim,victim)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertIn(source.card,sim.players[0].graveyard)
        self.assertNotIn(source.card,sim.players[0].hand)
        sim.invariant()
