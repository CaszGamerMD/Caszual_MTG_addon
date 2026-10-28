import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class CounterChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=s.RulesBridge()
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self,text='Counter target spell.'):
  raw=dict(name='Unknown denial',types=['Instant'],manaCost='{U}',oracleText=text)
  counter=s.import_diagnostic_card(self.rules,raw,1,'counter',{'Blue'})
  spell=s.Card('spell','Life spell','spell',mana_cost='{0}',life=5)
  land=s.Card('blue','Island','land',mask=2)
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[spell],s.demo_deck(1)+[counter,land]),diagnostic=True)
  for seat,cards in [(0,[spell]),(1,[counter,land])]:
   p=sim.players[seat]
   for c in cards:(p.hand if c in p.hand else p.library).remove(c)
  sim.players[0].hand.append(spell);sim.players[1].hand.append(counter);sim.players[1].battlefield.append(s.Permanent(land))
  sim.phase='main';sim.manual_priority=True;sim.cast_spell(0,spell);sim.pass_priority(0)
  return sim,spell,counter
 def test_counter_target_and_zones_no_effect(self):
  sim,spell,counter=self.fixture();self.assertEqual(counter.kind,'counter_spell')
  choices=sim.priority_observation(1).legal_actions
  action=next(a for a in choices if a.kind=='respond')
  sim.act_priority(1,action);sim.invariant()
  sim.pass_priority(1);sim.pass_priority(0)
  self.assertFalse(sim.stack.items)
  self.assertIn(spell,sim.players[0].graveyard);self.assertIn(counter,sim.players[1].graveyard)
  self.assertEqual(sim.players[0].life,40);sim.invariant()
 def test_filter_and_illegal_target_before_cost(self):
  sim,spell,counter=self.fixture('Counter target creature spell.')
  self.assertFalse(sim.counter_targets(counter))
  with self.assertRaises(ValueError):sim.cast_spell(1,counter,target=sim.stack.items[0].id)
  self.assertIn(counter,sim.players[1].hand);self.assertFalse(sim.players[1].battlefield[0].tapped)
 def test_target_gone_does_not_counter_another_object(self):
  sim,spell,counter=self.fixture();target=sim.stack.items[0].id
  sim.cast_spell(1,counter,target=target)
  # A second effect removes that target before this counterspell resolves.
  removed=sim.stack.counter(target);sim.players[0].graveyard.append(removed.payload[1])
  sim.pass_priority(1);sim.pass_priority(0)
  self.assertTrue(any(e['kind']=='illegal_target' for e in sim.events));sim.invariant()
 def test_countering_a_counterspell_preserves_original(self):
  sim,spell,counter=self.fixture()
  original_id=sim.stack.items[0].id
  sim.cast_spell(1,counter,target=original_id)
  first_counter_id=sim.stack.items[-1].id
  sim.pass_priority(1)
  removed=sim.players[0].library.pop()
  answer=s.import_diagnostic_card(self.rules,dict(name='Unknown answer',types=['Instant'],manaCost='{0}',oracleText='Counter target spell.'),0,removed.id,{'Blue'})
  sim.players[0].hand.append(answer)
  sim.cast_spell(0,answer,target=first_counter_id)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(len(sim.stack.items),1)
  self.assertEqual(sim.stack.items[0].id,original_id)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(sim.players[0].life,45)
  self.assertIn(counter,sim.players[1].graveyard);sim.invariant()
 def test_automated_player_casts_counter_response(self):
  sim,spell,counter=self.fixture()
  sim.manual_priority=False;sim.drain_priority()
  self.assertIn(counter,sim.players[1].graveyard)
  self.assertIn(spell,sim.players[0].graveyard)
  self.assertEqual(sim.players[0].life,40)
  self.assertTrue(any(d['phase']=='priority' and d['action']=='respond' and d['seat']==1 for d in sim.decisions))
  self.assertFalse(sim.stack.items);sim.invariant()
 def test_automated_counter_war_does_not_counter_own_spell(self):
  sim,spell,counter=self.fixture()
  removed=sim.players[0].library.pop()
  answer=s.import_diagnostic_card(self.rules,dict(name='Unknown answer',types=['Instant'],manaCost='{0}',oracleText='Counter target spell.'),0,removed.id,{'Blue'})
  sim.players[0].hand.append(answer)
  sim.manual_priority=False;sim.drain_priority()
  self.assertEqual(sim.players[0].life,45)
  replies=[d for d in sim.decisions if d['phase']=='priority' and d['action']=='respond']
  self.assertEqual([d['seat'] for d in replies],[1,0])
  self.assertEqual(len(sim.players[0].graveyard),2)
  self.assertFalse(sim.stack.items);sim.invariant()
 def test_rejects_additional_rules_and_costs(self):
  for text in ['Counter target spell unless its controller pays {2}.','Counter target spell. Draw a card.']:
   card=s.import_diagnostic_card(self.rules,dict(name='Unknown denial',types=['Instant'],manaCost='{U}',oracleText=text),0,'x',{'Blue'})
   self.assertEqual(card.kind,'unsupported')
