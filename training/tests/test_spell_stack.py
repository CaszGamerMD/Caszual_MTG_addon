import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class SpellStackChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=s.RulesBridge()
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  sorcery=s.Card('sorcery','Sorcery','spell',mana_cost='{1}',life=3)
  instant=s.import_diagnostic_card(self.rules,dict(name='Unknown instant',types=['Instant'],manaCost='{1}',oracleText='You gain 2 life.'),1,'instant',{'White'})
  land0=s.Card('land0','Wastes','land',mask=32);land1=s.Card('land1','Wastes','land',mask=32)
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[sorcery,land0],s.demo_deck(1)+[instant,land1]),diagnostic=True)
  for seat,spell,land in [(0,sorcery,land0),(1,instant,land1)]:
   p=sim.players[seat]
   for c in (spell,land):(p.hand if c in p.hand else p.library).remove(c)
   p.hand.append(spell);p.battlefield.append(s.Permanent(land))
  sim.phase='main';sim.manual_priority=True
  return sim,sorcery,instant
 def test_response_resolves_first_and_conserves_cards(self):
  sim,sorcery,instant=self.fixture();sim.cast_spell(0,sorcery)
  self.assertEqual(sim.players[0].life,40);self.assertFalse(sim.players[0].graveyard);sim.invariant()
  self.assertFalse(sim.response_choices(1))
  sim.pass_priority(0)
  self.assertIn(instant,sim.response_choices(1))
  observation=sim.priority_observation(1)
  self.assertEqual(observation.own_hand,tuple(sim.players[1].hand))
  response=next(a for a in observation.legal_actions if a.kind=='respond')
  sim.act_priority(1,response);sim.invariant()
  self.assertEqual([p.life for p in sim.players],[40,40])
  self.assertEqual(sim.stack.passes,0)
  sim.pass_priority(1);sim.pass_priority(0)
  self.assertEqual([p.life for p in sim.players],[40,42]);self.assertIn(instant,sim.players[1].graveyard)
  self.assertEqual(sim.stack.priority,0)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual([p.life for p in sim.players],[43,42]);self.assertIn(sorcery,sim.players[0].graveyard)
  sim.invariant()
 def test_sorcery_response_and_wrong_priority_rejected_without_payment(self):
  sim,sorcery,instant=self.fixture();sim.cast_spell(0,sorcery)
  before=list(sim.players[1].hand)
  with self.assertRaises(ValueError):sim.cast_spell(1,instant)
  self.assertEqual(before,sim.players[1].hand);self.assertFalse(sim.players[1].battlefield[0].tapped)
  sim.pass_priority(0)
  from dataclasses import replace
  fake=replace(instant,instant=False)
  sim.players[1].hand[-1]=fake
  with self.assertRaises(ValueError):sim.cast_spell(1,fake)
  self.assertFalse(sim.players[1].battlefield[0].tapped)
