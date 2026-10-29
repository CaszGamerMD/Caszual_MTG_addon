import sys,json,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class RemovalChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=s.RulesBridge()
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  deck=json.loads((Path(__file__).resolve().parents[1]/'decks/8321184-squirrels.json').read_text())
  raw=next(c for c in deck['mainboard'] if c['name']=='Nested Shambler')
  target=s.import_diagnostic_card(self.rules,raw,0,'target',{'Black'})
  removal=s.import_diagnostic_card(self.rules,dict(name='Unknown removal',types=['Instant'],manaCost='{0}',oracleText='Destroy target creature.'),1,'remove',{'Black'})
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[target],s.demo_deck(1)+[removal]),diagnostic=True)
  for seat,card in [(0,target),(1,removal)]:
   p=sim.players[seat];(p.hand if card in p.hand else p.library).remove(card)
  sim.enter_creature(target,sim.players[0]);sim.players[1].hand.append(removal)
  sim.manual_priority=True;sim.phase='main';sim.stack.priority=1
  return sim,target,removal
 def resolve(self,sim):
  while sim.stack.items:
   sim.pass_priority(sim.stack.priority)
 def test_destroy_then_death_ability_waits_on_stack(self):
  sim,target,removal=self.fixture();self.assertEqual(removal.kind,'removal_spell')
  action=next(a for a in sim.priority_observation(1).legal_actions if a.target_permanent==target.id)
  sim.act_priority(1,action)
  self.assertTrue(sim.players[0].battlefield)
  sim.pass_priority(1);sim.pass_priority(0)
  self.assertIn(target,sim.players[0].graveyard)
  self.assertFalse(sim.players[0].battlefield)
  self.assertEqual(len(sim.stack.items),1)
  self.resolve(sim)
  self.assertEqual(len(sim.players[0].battlefield),1)
  self.assertTrue(sim.players[0].battlefield[0].card.is_token)
  self.assertTrue(sim.players[0].battlefield[0].tapped);sim.invariant()
 def test_indestructible_can_be_targeted_but_survives(self):
  sim,target,removal=self.fixture();p=sim.players[0].battlefield[0]
  p.card=replace(p.card,event_definition=replace(p.card.event_definition,abilities=frozenset({'indestructible'})))
  sim.cast_spell(1,removal,target=target.id);self.resolve(sim)
  self.assertEqual(len(sim.players[0].battlefield),1)
  self.assertFalse(sim.players[0].graveyard);sim.invariant()
 def test_departed_target_does_not_resolve_or_retarget(self):
  sim,target,removal=self.fixture();sim.cast_spell(1,removal,target=target.id)
  sim.send_to_destination(sim.players[0],sim.players[0].battlefield[0])
  self.resolve(sim)
  self.assertTrue(any(e['kind']=='illegal_target' for e in sim.events))
  self.assertFalse(sim.players[0].battlefield);sim.invariant()
 def test_removed_attacker_does_not_stall_combat(self):
  sim,target,removal=self.fixture();sim.cast_spell(1,removal,target=target.id);self.resolve(sim)
  sim.manual_priority=False;sim.phase='block';sim.pending=target.id
  sim.step()
  self.assertEqual(sim.phase,'second_main');self.assertIsNone(sim.pending);sim.invariant()
 def test_missing_target_and_additional_text_rejected(self):
  sim,target,removal=self.fixture()
  with self.assertRaises(ValueError):sim.cast_spell(1,removal,target='absent')
  self.assertIn(removal,sim.players[1].hand)
  raw=dict(name='Unknown removal',types=['Instant'],manaCost='{0}',oracleText='Destroy target creature. Its controller draws a card.')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,1,'bad',{'Black'}).kind,'unsupported')
