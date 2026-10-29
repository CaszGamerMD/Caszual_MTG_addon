"""Board damage affects planeswalker loyalty and counts each permanent once."""
import json,sys,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
class PlaneswalkerDamageChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.raw=next(c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard'] if c['name']=='Goblin Chainwhirler')
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  source=s.import_diagnostic_card(self.rules,self.raw,0,'chain',{'Red'})
  cards=[]
  for uid,loyalty,text,types in [('fragile',1,'',['Planeswalker']),('durable',3,'',['Planeswalker']),('indestructible',1,'Indestructible',['Planeswalker']),('dual',3,'',['Creature','Planeswalker'])]:
   raw=dict(name=uid,types=types,loyalty=str(loyalty),oracleText=text,manaCost='{0}',power='2' if 'Creature' in types else '',toughness='2' if 'Creature' in types else '')
   card=s.import_diagnostic_card(self.rules,raw,1,uid,set())
   self.assertNotEqual(card.kind,'unsupported');cards.append(card)
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[source],s.demo_deck(1)+cards),diagnostic=True)
  for seat,chosen in ((0,[source]),(1,cards)):
   p=sim.players[seat]
   for c in chosen:(p.hand if c in p.hand else p.library).remove(c)
  sim.enter_creatures(cards,sim.players[1]);sim.manual_priority=True;sim.phase='main'
  pending=sim.enter_creature(source,sim.players[0]);sim.resolve_entry_triggers(pending,source)
  return sim,source,cards
 def resolve(self,sim):sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
 def test_real_chainwhirler_damages_player_creatures_and_planeswalkers(self):
  sim,source,cards=self.fixture();self.resolve(sim)
  self.assertEqual(sim.players[1].life,39)
  self.assertEqual({c.id for c in sim.players[1].graveyard},{'fragile','indestructible'})
  self.assertEqual({p.card.id:p.loyalty for p in sim.players[1].battlefield},{'durable':2,'dual':2})
  self.assertEqual(next(p for p in sim.players[1].battlefield if p.card.id=='dual').marked_damage,1)
  self.assertEqual(next(p for p in sim.players[1].battlefield if p.card.id=='durable').marked_damage,0)
  sim.invariant();json.dumps(sim.report())
 def test_lifelink_and_deathtouch_count_dual_type_permanent_once(self):
  sim,source,cards=self.fixture();item=sim.players[0].battlefield[0]
  item.card=replace(item.card,event_definition=replace(item.card.event_definition,abilities=frozenset({'lifelink','deathtouch'})))
  self.resolve(sim)
  self.assertEqual(sim.players[0].life,45) # one player plus four distinct permanents
  self.assertEqual({c.id for c in sim.players[1].graveyard},{'fragile','indestructible','dual'})
  self.assertEqual(sim.players[1].battlefield[0].card.id,'durable');sim.invariant()
 def test_zero_loyalty_state_based_action_ignores_indestructible(self):
  sim,source,cards=self.fixture()
  item=next(p for p in sim.players[1].battlefield if p.card.id=='indestructible');item.loyalty=0
  sim.resolve_entry_triggers([],source)
  self.assertNotIn(item,sim.players[1].battlefield)
  sim.invariant()
 def test_noncreature_planeswalkers_do_not_trigger_creature_death_watchers(self):
  sim,source,cards=self.fixture()
  raw=dict(name='Death watcher',types=['Enchantment'],manaCost='{0}',oracleText='Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life.')
  watcher=s.import_diagnostic_card(self.rules,raw,1,'watch',set())
  sim.enter_creature(replace(watcher,is_token=True),sim.players[1])
  self.resolve(sim)
  self.assertFalse(sim.stack.items);self.assertEqual(sim.players[0].life,40)
 def test_unknown_planeswalker_abilities_remain_blocked(self):
  raw=dict(name='Unknown walker',types=['Planeswalker'],manaCost='{2}{U}',loyalty='3',oracleText='+1: Draw a card.')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Blue'}).kind,'unsupported')
  raw['oracleText']='';raw['loyalty']='X'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Blue'}).kind,'unsupported')
