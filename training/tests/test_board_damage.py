import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
class BoardDamageChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  source=s.import_diagnostic_card(self.rules,self.lookup['Goblin Chainwhirler'],0,'chain',{'Red'})
  self.assertEqual(source.kind,'creature')
  enemies=[s.import_diagnostic_card(self.rules,self.lookup[name],1,'enemy'+str(i),{'Black','Green'}) for i,name in enumerate(['Blood Artist','Nested Shambler'])]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[source],s.demo_deck(1)+enemies),diagnostic=True)
  for seat,cards in [(0,[source]),(1,enemies)]:
   for card in cards:
    p=sim.players[seat];(p.hand if card in p.hand else p.library).remove(card)
  for card in enemies:sim.enter_creature(card,sim.players[1])
  for ident,toughness,abilities in [('survivor',2,set()),('indestructible',1,{'indestructible'})]:
   d=s.EventDefinition(ident,frozenset({'Creature'}),frozenset(),False,1,toughness,frozenset(abilities))
   c=s.Card(ident,ident,'creature',traits=f'1;{toughness};',power=1,toughness=toughness,event_definition=d,is_token=True)
   sim.enter_creature(c,sim.players[1])
  sim.manual_priority=True;triggers=sim.enter_creature(source,sim.players[0]);sim.resolve_entry_triggers(triggers,source)
  return sim,source,enemies
 def test_real_damage_simultaneous_deaths_marks_and_triggers(self):
  sim,source,enemies=self.fixture()
  self.assertEqual(sim.players[1].life,40)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual({p.card.id for p in sim.players[1].battlefield},{'survivor','indestructible'})
  self.assertTrue(all(p.marked_damage==1 for p in sim.players[1].battlefield))
  self.assertEqual(sim.players[1].life,39)
  self.assertEqual(len(sim.stack.items),3)
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  self.assertEqual([p.life for p in sim.players],[38,41])
  self.assertEqual(len(sim.players[1].battlefield),3)
  self.assertEqual(sim.players[0].battlefield[0].marked_damage,0)
  sim.invariant()
 def test_source_leaving_does_not_cancel_damage_and_player_loss_stops_triggers(self):
  sim,source,enemies=self.fixture()
  from dataclasses import replace
  item=sim.players[0].battlefield[0]
  item.card=replace(item.card,event_definition=replace(item.card.event_definition,abilities=frozenset({'lifelink','deathtouch'})))
  sim.send_to_destination(sim.players[0],sim.players[0].battlefield[0])
  sim.players[1].life=1
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(sim.winner,0)
  self.assertEqual(sim.players[0].life,45)
  self.assertFalse(sim.stack.items)
  self.assertEqual({c.id for c in sim.players[1].graveyard},{c.id for c in enemies})
  sim.invariant()
 def test_normal_combat_includes_prior_noncombat_damage(self):
  from dataclasses import replace
  from unittest.mock import patch
  sim,source,enemies=self.fixture()
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  attacker=sim.players[0].battlefield[0]
  attacker.card=replace(attacker.card,event_definition=replace(attacker.card.event_definition,power=1,abilities=frozenset()))
  sim.manual_priority=False;sim.phase='block';sim.pending=source.id
  with patch.object(sim,'decide',return_value=s.Candidate('survivor','block',card_id='survivor')):sim.step()
  self.assertEqual(sim.phase,'regular_damage')
  sim.step()
  self.assertFalse(any(p.card.id=='survivor' for p in sim.players[1].battlefield))
  sim.invariant()
 def test_unfamiliar_amount_and_keyword_composition(self):
  raw=dict(name='Unknown wave',types=['Creature'],power='2',toughness='2',manaCost='{R}',oracleText='Lifelink\nWhen this creature enters, this creature deals 2 damage to each opponent and each creature and planeswalker they control.')
  card=s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'})
  self.assertEqual(card.kind,'creature');self.assertEqual(card.event_definition.triggers[0].effect.amount,2)
  raw['oracleText']+=' Draw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'}).kind,'unsupported')
