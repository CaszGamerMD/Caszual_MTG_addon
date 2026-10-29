"""Legendary selectors and stack-based mana ward costs."""
import sys,json,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import parse_card
class WardChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.raw=next(c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard'] if c['name']=='Flowering of the White Tree')
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self,mana=2):
  tree=s.import_diagnostic_card(self.rules,self.raw,0,'tree',{'White'});self.assertEqual(tree.kind,'enchantment')
  target=s.Card('target','Legend','creature','{0}','2;2;',2,2,legendary=True)
  removal=s.import_diagnostic_card(self.rules,dict(name='Unknown removal',manaCost='{B}',types=['Instant'],oracleText='Destroy target creature.'),1,'removal',{'Black'})
  lands=[s.Card('mana'+str(i),'Swamp','land',mask=4) for i in range(mana)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[tree,target],s.demo_deck(1)+[removal]+lands),diagnostic=True)
  for seat,cards in ((0,[tree,target]),(1,[removal]+lands)):
   p=sim.players[seat]
   for c in cards:(p.hand if c in p.hand else p.library).remove(c)
  sim.enter_creature(tree,sim.players[0]);sim.enter_creature(target,sim.players[0])
  sim.players[1].hand.append(removal);sim.players[1].battlefield.extend(s.Permanent(c) for c in lands)
  sim.phase='main';sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.manual_priority=True
  return sim,tree,target,removal
 def resolve(self,sim):sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
 def test_legendary_and_nonlegendary_bonuses_are_disjoint(self):
  sim,tree,target,removal=self.fixture()
  common=s.Card('common','Common','creature','{0}','2;2;',2,2,is_token=True)
  sim.enter_creature(common,sim.players[0]);sim.enter_creature(replace(common,id='enemy',legendary=True),sim.players[1])
  game=sim.event_game('main')
  self.assertEqual(game.stats(game.battlefield[target.id]),(4,3))
  self.assertEqual(game.stats(game.battlefield['common']),(3,3))
  self.assertEqual(game.stats(game.battlefield['enemy']),(2,2))
  self.assertEqual(game.ward_costs(game.battlefield[target.id]),('{1}',))
  self.assertFalse(game.ward_costs(game.battlefield['common']))
  self.assertFalse(game.ward_costs(game.battlefield[tree.id]));sim.invariant()
 def test_mana_paid_only_when_ward_resolves_then_spell_can_resolve(self):
  sim,tree,target,removal=self.fixture()
  sim.cast_spell(1,removal,target=target.id)
  self.assertEqual(sim.stack.priority,1);self.assertEqual(len(sim.stack.items),2)
  self.assertEqual(sum(p.tapped for p in sim.players[1].battlefield),1)
  self.resolve(sim)
  self.assertEqual(len(sim.stack.items),1)
  self.assertEqual(sum(p.tapped for p in sim.players[1].battlefield),2)
  self.assertTrue(any(p.card.id==target.id for p in sim.players[0].battlefield))
  self.resolve(sim)
  self.assertIn(target,sim.players[0].graveyard)
  self.assertTrue(any(e['kind']=='ward_paid' for e in sim.events));json.dumps(sim.report());sim.invariant()
 def test_unpaid_ward_counters_and_policy_anticipates_cost(self):
  sim,tree,target,removal=self.fixture(mana=1)
  choice=next(c for c in sim.removal_choices(1,removal,'cast') if c.target_permanent==target.id)
  self.assertLess(sum(w*f for w,f in zip(sim.policies[1].weights,choice.features)),0)
  sim.cast_spell(1,removal,target=target.id);self.resolve(sim)
  self.assertFalse(sim.stack.items);self.assertIn(removal,sim.players[1].graveyard)
  self.assertNotIn(target,sim.players[0].graveyard)
  self.assertTrue(any(e['kind']=='ward_counter' for e in sim.events));sim.invariant()
 def test_multiple_instances_are_separate_and_survive_grant_source_departure(self):
  sim,tree,target,removal=self.fixture(mana=2)
  extra=s.Card('extra','Extra ward','enchantment',event_definition=replace(tree.event_definition,name='Extra ward'),is_token=True)
  sim.enter_creature(extra,sim.players[0])
  sim.cast_spell(1,removal,target=target.id)
  self.assertEqual(len(sim.stack.items),3)
  sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield if p.card.id==tree.id))
  self.resolve(sim);self.assertEqual(len(sim.stack.items),2)
  self.resolve(sim);self.assertFalse(sim.stack.items)
  self.assertTrue(any(p.card.id==target.id for p in sim.players[0].battlefield));sim.invariant()
 def test_countered_original_does_not_spend_ward_payment(self):
  sim,tree,target,removal=self.fixture()
  sim.cast_spell(1,removal,target=target.id)
  spell=sim.stack.items[0];sim.counter_stack_item(spell)
  before=sum(p.tapped for p in sim.players[1].battlefield)
  self.resolve(sim)
  self.assertEqual(sum(p.tapped for p in sim.players[1].battlefield),before)
  self.assertTrue(any(e['kind']=='ward_no_target' for e in sim.events));sim.invariant()
 def test_own_target_and_untargeted_sweep_do_not_trigger_ward(self):
  sim,tree,target,removal=self.fixture()
  frame=sim.stack.push(0,({'operation':'ability'},tree),'Friendly ability')
  self.assertFalse(sim.target_triggers(frame,target.id))
  sim.stack.counter(frame.id)
  self.assertFalse(sim.target_triggers(frame,None));sim.invariant()
 def test_intrinsic_ward_unfamiliar_amounts_and_remainder_rejection(self):
  raw=dict(name='Unknown warder',types=['Creature'],manaCost='{W}',power='2',toughness='2',oracleText='Ward {2}{U}')
  card=s.import_diagnostic_card(self.rules,raw,0,'intrinsic',{'White','Blue'})
  self.assertEqual(card.kind,'creature');self.assertEqual(card.event_definition.static_effects[0].ward_cost,'{2}{U}')
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'intrinsic',{'White','Blue'}).kind,'unsupported')
  raw=dict(self.raw,name='Unknown anthem',oracleText='Legendary creatures you control get +3/+2 and have ward {2}.\nNonlegendary creatures you control get +2/+1.')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'anthem',{'White'}).kind,'enchantment')
