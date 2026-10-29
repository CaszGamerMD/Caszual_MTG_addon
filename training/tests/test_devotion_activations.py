"""Generic devotion/type transitions and mana-costed token abilities."""
import json,sys,unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import parse_card, Game, Permanent

class DevotionActivationChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge()
  cls.raw=next(c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard'] if c['name']=='Heliod, God of the Sun')
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  heliod=s.import_diagnostic_card(self.rules,self.raw,0,'god',{'White'})
  self.assertEqual(heliod.kind,'creature')
  lands=[s.Card(f'mana{i}','Plains','land',mask=1) for i in range(8)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[heliod]+lands,s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for c in [heliod]+lands:(p.hand if c in p.hand else p.library).remove(c)
  p.battlefield.extend(s.Permanent(c) for c in lands)
  sim.enter_creature(heliod,p);sim.manual_priority=True;sim.phase='main'
  return sim,heliod
 def add_white(self,sim,cost='{W}{W}{W}{W}'):
  c=s.Card('devotion','White permanent','creature',cost,traits='1;1;',power=1,toughness=1,is_token=True)
  sim.enter_creature(c,sim.players[0]);return sim.players[0].battlefield[-1]
 def test_creature_type_recomputed_from_permanents_and_own_cost(self):
  sim,card=self.fixture();god=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertIsNone(sim.effective_card(god));self.assertNotIn(card.id,{p.card.id for _,p in sim.creature_targets()})
  self.assertFalse(sim.display_permanent(god)['isCreature'])
  white=self.add_white(sim)
  self.assertEqual(sim.effective_card(god).power,5)
  self.assertIn('vigilance',sim.effective_card(white).traits)
  self.assertNotIn('vigilance',sim.effective_card(god).traits)
  sim.send_to_destination(sim.players[0],white)
  self.assertIsNone(sim.effective_card(god));self.assertIn(god,sim.players[0].battlefield);sim.invariant()
 def test_devotion_counts_mana_symbols_not_colors_or_rules_text(self):
  definition=parse_card(self.raw);game=Game();god=Permanent('god',definition,0);game.enter(god)
  self.assertEqual(game.devotion(0,'W'),1)
  # White hybrid/Phyrexian symbols count once each; generic/colorless do not.
  other=replace(definition,name='Other',mana_cost='{W/U}{2/W}{W/P}{C}{3}',devotion=())
  game.enter(Permanent('other',other,0))
  game.enter(Permanent('enemy',replace(other,mana_cost='{W}{W}{W}'),1))
  self.assertEqual(game.devotion(0,'W'),4);self.assertFalse(game.creature(god))
  game.enter(Permanent('fifth',replace(other,mana_cost='{W}'),0));self.assertTrue(game.creature(god))
 def test_tokens_wait_for_passes_keep_enchantment_type_and_cost_no_devotion(self):
  sim,card=self.fixture()
  self.assertTrue(any(a.kind=='activate_tokens' for a in sim.legal(0)))
  sim.activate_tokens(0,card.id)
  self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),4)
  self.assertEqual(len(sim.creature_targets()),0)
  sim.pass_priority(0);sim.pass_priority(1)
  token=next(p for p in sim.players[0].battlefield if p.card.is_token)
  self.assertEqual(token.card.event_definition.types,frozenset({'Enchantment','Creature'}))
  self.assertEqual((token.card.power,token.card.toughness),(2,1))
  self.assertIn('vigilance',sim.effective_card(token).traits)
  self.assertEqual(sim.event_game('main').devotion(0,'W'),1);sim.invariant()
  json.dumps(sim.report())
 def test_off_turn_priority_and_source_departure_do_not_cancel_ability(self):
  sim,card=self.fixture();sim.active=1;sim.stack.active=1;sim.stack.priority=0
  self.assertTrue(any(a.kind=='activate_tokens' for a in sim.priority_observation(0).legal_actions))
  sim.activate_tokens(0,card.id)
  self.assertEqual(sim.stack.priority,0)
  god=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  sim.send_to_destination(sim.players[0],god)
  sim.pass_priority(0);sim.pass_priority(1)
  token=next(p for p in sim.players[0].battlefield if p.card.is_token)
  self.assertNotIn('vigilance',sim.effective_card(token).traits);sim.invariant()
 def test_unfamiliar_names_amounts_colors_and_unparsed_remainder(self):
  raw=dict(self.raw,name='Unknown, Maker',manaCost='{G}',oracleText="Indestructible\nAs long as your devotion to green is less than three, Unknown isn't a creature.\nOther creatures you control have trample.\n{1}{G}: Create two 3/2 green Beast creature tokens.")
  card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
  self.assertEqual(card.kind,'creature');self.assertEqual(card.event_definition.devotion,('G',3))
  self.assertEqual(card.event_definition.activations[0][1].amount,2)
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'}).kind,'unsupported')
 def test_cannot_activate_without_priority_or_colored_payment(self):
  sim,card=self.fixture();sim.stack.priority=1
  with self.assertRaises(ValueError):sim.activate_tokens(0,card.id)
  sim.stack.priority=0
  for p in sim.players[0].battlefield:
   if p.card.kind=='land':p.card=replace(p.card,mask=2)
  with self.assertRaises(ValueError):sim.activate_tokens(0,card.id)
  self.assertFalse(any(p.tapped for p in sim.players[0].battlefield));self.assertFalse(sim.stack.items)

 def test_devotion_at_entry_controls_creature_entry_triggers(self):
  watcher=parse_card(dict(name='Watcher',types=['Enchantment'],oracleText='Whenever a creature you control enters, this enchantment deals 1 damage to each opponent.'))
  game=Game();game.enter(Permanent('watch',watcher,0))
  god=Permanent('low',parse_card(self.raw),0);game.enter(god)
  self.assertFalse(any(e['kind']=='trigger' for e in game.events))
  # A different permanent already provides four white symbols before entry.
  game=Game();game.enter(Permanent('watch',watcher,0))
  game.enter(Permanent('white',replace(watcher,mana_cost='{W}{W}{W}{W}',triggers=()),0))
  game.enter(Permanent('high',parse_card(self.raw),0))
  self.assertEqual(sum(e['kind']=='trigger' for e in game.events),1)
 def test_losing_creature_type_removes_aura_and_detaches_equipment(self):
  sim,card=self.fixture();white=self.add_white(sim)
  for kind in ('aura','equipment'):
   d=s.EventDefinition(kind,frozenset({'Enchantment'} if kind=='aura' else {'Artifact'}),frozenset(),False,0,0,frozenset(),attachment=(kind,'{1}',frozenset({'lifelink'}),0,0))
   c=s.Card(kind,kind,kind,event_definition=d,is_token=True)
   sim.enter_creature(c,sim.players[0]);sim.players[0].battlefield[-1].attached_to=card.id
  sim.destroy_batch(((0,white),),white.card)
  self.assertFalse(any(p.card.kind=='aura' for p in sim.players[0].battlefield))
  equipment=next(p for p in sim.players[0].battlefield if p.card.kind=='equipment')
  self.assertIsNone(equipment.attached_to);sim.invariant()

 def test_colored_artifact_mana_cost_counts_but_its_production_does_not(self):
  sim,card=self.fixture()
  raw=dict(name='White mana artifact',types=['Artifact'],manaCost='{W}{W}{W}{W}',oracleText='{T}: Add {W}.')
  artifact=s.import_diagnostic_card(self.rules,raw,0,'white-orb',{'White'})
  self.assertEqual(artifact.kind,'mana_artifact')
  sim.players[0].battlefield.append(s.Permanent(replace(artifact,is_token=True)))
  game=sim.event_game('main')
  self.assertEqual(game.devotion(0,'W'),5)
  self.assertTrue(game.creature(game.battlefield[card.id]));sim.invariant()
