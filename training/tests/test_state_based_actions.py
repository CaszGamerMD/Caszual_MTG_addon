"""Rules 704.3, 704.5f/g: repeat death batches before trigger placement."""
import sys, unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import Selector, StaticEffect, Trigger, Effect

class StateBasedChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=s.RulesBridge()
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  sim=s.Simulator(self.rules,42,diagnostic=True)
  sim.manual_priority=True;sim.phase='main'
  return sim
 def token(self,sim,identifier,seat=0,toughness=1,abilities=(),subtype='',effects=(),triggers=()):
  d=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset({subtype} if subtype else ()),False,1,toughness,
      frozenset(abilities),static_effects=effects,triggers=triggers)
  c=s.Card(identifier,identifier,'creature',mana_cost='{0}',traits=f'1;{toughness};',power=1,toughness=toughness,event_definition=d,is_token=True)
  sim.enter_creature(c,sim.players[seat])
  return next(p for p in sim.players[seat].battlefield if p.card.id==identifier)
 def test_three_batches_finish_before_any_trigger_is_stacked(self):
  sim=self.fixture()
  a=self.token(sim,'first',effects=(StaticEffect(Selector(subtype='Second'),0,1),))
  b=self.token(sim,'second',seat=1,subtype='Second',effects=(StaticEffect(Selector(subtype='Third'),0,1),))
  c=self.token(sim,'third',subtype='Third')
  watcher=self.token(sim,'watcher',seat=1,toughness=4,
      triggers=(Trigger('dies',Selector(creature=True),Effect('lose_life',1,gain=1)),))
  for item in (a,b,c):item.marked_damage=1
  sim.resolve_entry_triggers([],a.card)
  self.assertEqual([p.card.id for player in sim.players for p in player.battlefield],['watcher'])
  batches=[e for e in sim.events if e['kind']=='state_based_deaths']
  self.assertEqual([e['details']['deaths'] for e in batches],[['first'],['second'],['third']])
  pushes=[e for e in sim.events if e['kind']=='stack_push']
  self.assertEqual(len(pushes),3)
  self.assertGreater(min(e['index'] for e in pushes),batches[-1]['index'])
  self.assertEqual([p.life for p in sim.players],[40,40])
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  self.assertEqual([p.life for p in sim.players],[37,43]);sim.invariant()
 def test_zero_toughness_ignores_indestructible_but_damage_does_not(self):
  sim=self.fixture()
  self.token(sim,'zero',toughness=0,abilities=('indestructible',))
  survivor=self.token(sim,'durable',abilities=('indestructible',));survivor.marked_damage=20
  sim.resolve_entry_triggers([],survivor.card)
  self.assertEqual([p.card.id for p in sim.players[0].battlefield],['durable']);sim.invariant()
 def test_loss_of_anthem_to_removal_kills_previously_damaged_creature(self):
  sim=self.fixture()
  lord=self.token(sim,'lord',effects=(StaticEffect(Selector(other=True,creature=True,relation='controller'),0,1),))
  follower=self.token(sim,'follower');follower.marked_damage=1
  sim.destroy_batch(((0,lord),),lord.card)
  self.assertFalse(sim.players[0].battlefield)
  sim.invariant()
 def test_checks_wait_until_whole_ability_finishes(self):
  sim=self.fixture();item=self.token(sim,'temporary-zero',toughness=0)
  sim._resolving_stack=True
  sim.resolve_entry_triggers([],item.card)
  self.assertIn(item,sim.players[0].battlefield)
  item.counters=1
  sim._resolving_stack=False;sim.resolve_entry_triggers([],item.card)
  self.assertIn(item,sim.players[0].battlefield);self.assertFalse(sim.stack.items)
 def test_cleanup_removes_temporary_toughness_then_checks(self):
  sim=self.fixture();item=self.token(sim,'cleanup-zero',toughness=0)
  item.temporary_toughness=1
  sim.phase='cleanup';sim.step()
  self.assertFalse(sim.players[0].battlefield);sim.invariant()

 def test_zero_toughness_entry_dies_before_its_ability_gets_priority(self):
  raw=dict(name='Unknown fragile spark',types=['Creature'],power='0',toughness='0',manaCost='{0}',
      oracleText='When this creature enters, this creature deals 2 damage to each opponent.')
  card=s.import_diagnostic_card(self.rules,raw,0,'fragile',{'Red'})
  self.assertEqual(card.kind,'creature')
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
  player=sim.players[0]
  if card in player.library:player.library.remove(card);player.hand.append(card)
  sim.manual_priority=True;sim.phase='main'
  sim.cast_spell(0,card)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertIn(card,player.graveyard)
  self.assertEqual(len(sim.stack.items),1)
  self.assertEqual(sim.players[1].life,40)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(sim.players[1].life,38);sim.invariant()
