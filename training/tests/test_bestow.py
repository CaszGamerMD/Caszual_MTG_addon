"""Bestow alternate cost, Aura stack type, and attachment/type transitions."""
import json,sys,unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
class BestowChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  card=s.import_diagnostic_card(self.rules,self.lookup['Hopeful Eidolon'],0,'eidolon',{'White'})
  self.assertEqual(card.kind,'creature')
  target=s.Card('target','Host','creature','{0}','2;2;',2,2)
  lands=[s.Card('land'+str(i),'Plains','land',mask=1) for i in range(6)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card,target]+lands,s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for c in [card,target]+lands:(p.hand if c in p.hand else p.library).remove(c)
  p.hand.append(card);sim.enter_creature(target,p);p.battlefield.extend(s.Permanent(c) for c in lands)
  sim.manual_priority=True;sim.phase='main'
  return sim,card,p.battlefield[0]
 def resolve(self,sim):sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
 def test_both_cast_modes_offered_with_different_costs_and_stack_types(self):
  sim,card,target=self.fixture()
  self.assertTrue(any(c.kind=='bestow' for c in sim.legal(0)))
  self.assertTrue(any(c.kind=='cast' and c.card_id==card.id for c in sim.legal(0)))
  sim.cast_spell(0,card,target=target.card.id,bestow=True)
  self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),4)
  creature=s.Card('c','Counter creature','counter_spell',counter_filter='creature')
  noncreature=replace(creature,counter_filter='noncreature')
  self.assertFalse(sim.counter_targets(creature));self.assertEqual(len(sim.counter_targets(noncreature)),1)
  self.resolve(sim)
  aura=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertIsNone(sim.effective_card(aura));self.assertTrue(aura.bestowed)
  self.assertEqual(sim.effective_card(target).power,3)
  self.assertIn('lifelink',sim.effective_card(target).traits)
  self.assertEqual(aura.card.mana_cost,'{W}')
  self.assertEqual(sim.event_game('main').devotion(0,'W'),1);sim.invariant()
 def test_normal_cast_is_a_creature_for_one_white_mana(self):
  sim,card,target=self.fixture();sim.cast_spell(0,card)
  self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),1)
  self.resolve(sim)
  item=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertFalse(item.bestowed);self.assertEqual(sim.effective_card(item).power,1)
  self.assertIn('lifelink',sim.effective_card(item).traits)
  self.assertEqual(sim.effective_card(target).power,2)
 def test_missing_target_resolves_as_creature_instead_of_fizzling(self):
  sim,card,target=self.fixture();sim.cast_spell(0,card,target=target.card.id,bestow=True)
  sim.send_to_destination(sim.players[0],target);self.resolve(sim)
  item=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertFalse(item.bestowed);self.assertEqual(sim.effective_card(item).power,1)
  self.assertNotIn(card,sim.players[0].graveyard);sim.invariant()
 def test_host_death_ends_bestow_without_new_entry_or_controller_change(self):
  sim,card,target=self.fixture();sim.cast_spell(0,card,target=target.card.id,bestow=True);self.resolve(sim)
  item=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  item.fresh=False;item.counters=2
  before=len(sim.events);sim.destroy_batch(((0,target),),target.card)
  self.assertIn(item,sim.players[0].battlefield);self.assertFalse(item.bestowed);self.assertFalse(item.fresh)
  self.assertEqual(sim.effective_card(item).power,3)
  self.assertFalse(any(e['kind']=='bestow_creature' for e in sim.events[before:]));sim.invariant()
 def test_type_change_of_host_ends_bestow_and_it_does_not_reattach(self):
  sim,card,target=self.fixture();sim.cast_spell(0,card,target=target.card.id,bestow=True);self.resolve(sim)
  target.card=replace(target.card,event_definition=s.EventDefinition('Host',frozenset({'Enchantment'}),frozenset(),False,2,2,frozenset()))
  sim.resolve_entry_triggers([],target.card)
  item=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertFalse(item.bestowed);self.assertIsNone(item.attached_to)
  self.assertIsNotNone(sim.effective_card(item));sim.invariant()
 def test_simultaneous_sweep_kills_bestowed_enchantment_once(self):
  sim,card,target=self.fixture();sim.cast_spell(0,card,target=target.card.id,bestow=True);self.resolve(sim)
  targets=sim.nonland_destruction_set(1);self.assertEqual(len(targets),2)
  sim.destroy_batch(targets,target.card)
  self.assertEqual(sum(c.id==card.id for c in sim.players[0].graveyard),1)
  self.assertFalse(sim.players[0].battlefield[0].card.kind=='creature');sim.invariant()
 def test_unfamiliar_name_stats_and_full_text_rejection(self):
  raw=dict(self.lookup['Hopeful Eidolon'],name='Unknown emissary',power='2',toughness='3',oracleText='Bestow {2}{G}\nTrample\nEnchanted creature gets +2/+3 and has trample.')
  card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'})
  self.assertEqual(card.kind,'creature');self.assertEqual(card.event_definition.bestow[0],'{2}{G}')
  self.assertEqual(card.event_definition.bestow[2][3:],(2,3))
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Green'}).kind,'unsupported')
 def test_requires_legal_target_and_base_card_with_bestow(self):
  sim,card,target=self.fixture()
  with self.assertRaises(ValueError):sim.cast_spell(0,card,target='missing',bestow=True)
  with self.assertRaises(ValueError):sim.cast_spell(0,target.card,target=target.card.id,bestow=True)
  self.assertIn(card,sim.players[0].hand);self.assertFalse(sim.stack.items)

 def test_bestow_entry_and_detachment_do_not_trigger_creature_entry(self):
  sim,card,target=self.fixture()
  watcher=s.import_diagnostic_card(self.rules,self.lookup['Impact Tremors'],0,'watcher',{'Red'})
  sim.enter_creature(replace(watcher,is_token=True),sim.players[0])
  sim.cast_spell(0,card,target=target.card.id,bestow=True);self.resolve(sim)
  self.assertEqual(sim.players[1].life,40);self.assertFalse(sim.stack.items)
  sim.destroy_batch(((0,target),),target.card)
  self.assertEqual(sim.players[1].life,40);self.assertFalse(sim.stack.items)
  json.dumps(sim.report());sim.invariant()
