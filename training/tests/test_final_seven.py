"""Actual seven-card Oracle programs and reusable cross-rule interactions."""
import sys,json,unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from advanced_simulator import root
NAMES=["Akroma's Memorial","Captain's Claws",'Cloudspire Coordinator','Ephemerate','Haazda Marshal','Lumen-Class Frigate','Skyknight Vanguard']
class FinalSevenChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self,names):
  cards=[s.import_diagnostic_card(self.rules,self.lookup[name],0,'card'+str(i),{'White','Red','Black','Green','Blue'}) for i,name in enumerate(names)]
  self.assertTrue(all(c.kind!='unsupported' for c in cards))
  lands=[s.Card('mana'+str(i),'Mana','land',mask=63) for i in range(10)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards+lands,s.demo_deck(1)),diagnostic=True);sim.manual_priority=True;sim.phase='main'
  p=sim.players[0]
  for c in cards+lands:(p.hand if c in p.hand else p.library).remove(c)
  p.battlefield.extend(s.Permanent(c) for c in lands)
  p.hand.extend(cards)
  for c in cards:
   if c.blink:continue
   else:
    p.hand.remove(c)
    pending=sim.enter_creature(c,p);sim.resolve_entry_triggers(pending,c)
  self.drain(sim)
  return sim,{c.name:c for c in cards}
 def drain(self,sim):
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
 def token(self,sim,identifier,seat=0,power=2,toughness=2,keywords=(),colors=(),subtypes=()):
  d=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(subtypes),False,power,toughness,frozenset(keywords),colors=frozenset(colors))
  c=s.Card(identifier,identifier,'creature','{0}',f'{power};{toughness};',power,toughness,event_definition=d,is_token=True,colors=tuple(colors))
  sim.enter_creature(c,sim.players[seat]);item=sim.players[seat].battlefield[-1];item.fresh=False;return item
 def ready(self,sim):
  for p in sim.players[0].battlefield:p.fresh=False
  sim.phase='attack';sim.stack.priority=sim.active
 def damage(self,sim):
  self.drain(sim)
  while sim.group_combat is not None:
   sim.group_damage_step();self.drain(sim)
 def test_all_seven_and_unfamiliar_names_compile_without_ignored_remainder(self):
  for index,name in enumerate(NAMES):
   raw=dict(self.lookup[name],name='Unfamiliar '+str(index))
   self.assertNotEqual(s.import_diagnostic_card(self.rules,raw,0,str(index),set()).kind,'unsupported',name)
   raw['oracleText']+='\nDraw an extra card at random.'
   self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,str(index),set()).kind,'unsupported',name)
 def test_vanguard_and_claws_tokens_attack_without_retriggering(self):
  sim,cards=self.fixture(['Skyknight Vanguard',"Captain's Claws"])
  v=cards['Skyknight Vanguard'];claws=cards["Captain's Claws"]
  sim.activate_equip(0,claws.id,v.id);self.drain(sim)
  self.ready(sim);sim.declare_attackers([v.id])
  self.assertEqual(len(sim.stack.items),2);self.drain(sim)
  tokens=[p for p in sim.players[0].battlefield if p.card.is_token]
  self.assertEqual(len(tokens),2);self.assertTrue(all(p.tapped and p.fresh for p in tokens))
  self.assertEqual(len(sim.group_combat['attackers']),3)
  self.assertEqual(sim.group_combat['declared'],[v.id])
  sim.declare_blockers({});self.damage(sim)
  self.assertEqual(sim.players[1].life,36) # equipped 2/2 plus two 1/1s
  sim.invariant();json.dumps(sim.report())
 def test_marshal_checks_declared_group_not_entering_attacking_tokens(self):
  sim,cards=self.fixture(['Haazda Marshal','Skyknight Vanguard'])
  self.ready(sim);sim.declare_attackers([c.id for c in cards.values()]);self.drain(sim)
  self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token]),1)
  sim.declare_blockers({});self.damage(sim)
  sim,cards=self.fixture(['Haazda Marshal','Skyknight Vanguard']);other=self.token(sim,'third')
  self.ready(sim);sim.declare_attackers([c.id for c in cards.values()]+[other.card.id]);self.drain(sim)
  soldier=next(p for p in sim.players[0].battlefield if p.card.is_token and p.card.id!='third' and 'lifelink' in p.card.event_definition.abilities)
  self.assertNotIn(soldier.card.id,sim.group_combat['attackers']);self.assertFalse(soldier.tapped)
 def test_attack_trigger_survives_source_leaving_and_token_can_be_blocked(self):
  sim,cards=self.fixture(['Skyknight Vanguard']);v=cards['Skyknight Vanguard'];self.ready(sim);sim.declare_attackers([v.id])
  sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield if p.card.id==v.id));self.drain(sim)
  token=next(p for p in sim.players[0].battlefield if p.card.is_token)
  blocker=self.token(sim,'blocker',1)
  sim.declare_blockers({token.card.id:[blocker.card.id]});self.damage(sim)
  self.assertEqual(sim.players[1].life,40);self.assertNotIn(token,sim.players[0].battlefield);sim.invariant()
 def test_group_damage_is_simultaneous_and_multiple_blockers_legal(self):
  sim,_=self.fixture([]);a=self.token(sim,'a',power=5,toughness=3);b=self.token(sim,'b',power=2,toughness=2)
  x=self.token(sim,'x',1);y=self.token(sim,'y',1)
  self.ready(sim);sim.declare_attackers(['a','b']);sim.declare_blockers({'a':['x','y']});self.damage(sim)
  self.assertEqual(sim.players[1].life,38)
  self.assertFalse(any(p.card.id in ('a','x','y') for player in sim.players for p in player.battlefield));sim.invariant()
 def test_first_strike_and_trample_deathtouch_with_multiple_blockers(self):
  sim,_=self.fixture([]);a=self.token(sim,'a',power=5,toughness=3,keywords=('double strike','trample','deathtouch'))
  self.token(sim,'x',1,power=4,toughness=8);self.token(sim,'y',1,power=4,toughness=8)
  self.ready(sim);sim.declare_attackers(['a']);sim.declare_blockers({'a':['x','y']})
  sim.group_damage_step();self.drain(sim)
  self.assertEqual(sim.players[1].life,37);self.assertIn(a,sim.players[0].battlefield)
  sim.group_damage_step();self.assertEqual(sim.players[1].life,32)
 def test_memorial_grants_all_keywords_and_forbids_black_red_blockers(self):
  sim,cards=self.fixture(["Akroma's Memorial"]);a=self.token(sim,'a');black=self.token(sim,'black',1,colors=('Black',),keywords=('flying',))
  game=sim.event_game('combat');state=game.battlefield['a']
  for ability in ('flying','first strike','vigilance','trample','haste','protection from black','protection from red'):self.assertTrue(game.has(state,ability),ability)
  self.ready(sim);sim.declare_attackers(['a']);self.assertFalse(a.tapped)
  with self.assertRaises(ValueError):sim.declare_blockers({'a':['black']})
 def test_protection_prevents_assigned_damage_but_not_trample_excess(self):
  sim,cards=self.fixture(["Akroma's Memorial"]);protected=self.token(sim,'protected',power=3,toughness=3)
  attacker=self.token(sim,'black',1,power=8,toughness=8,keywords=('trample',),colors=('Black',))
  sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
  sim.declare_attackers(['black']);sim.declare_blockers({'black':['protected']});self.damage(sim)
  self.assertEqual(sim.players[0].life,35);self.assertEqual(protected.marked_damage,0)
  self.assertEqual(attacker.marked_damage,3);sim.invariant()
 def test_protection_restricts_targeting_and_attachments_not_sweeps(self):
  sim,cards=self.fixture(["Akroma's Memorial"]);target=self.token(sim,'host')
  raw=dict(name='Black destroy',types=['Instant'],manaCost='{B}',oracleText='Destroy target creature.',colors=['Black'])
  removal=s.import_diagnostic_card(self.rules,raw,1,'black',{'Black'})
  self.assertNotIn('host',{p.card.id for _,p in sim.creature_targets(1,removal)})
  self.assertNotIn('host',{p.card.id for _,p in sim.creature_targets(0,removal)})
  self.assertIn(target,[p for _,p in sim.nonland_destruction_set(1)])
  sim.destroy_batch(sim.nonland_destruction_set(1),cards["Akroma's Memorial"]);self.assertNotIn(target,sim.players[0].battlefield)
 def test_history_counts_union_once_includes_earlier_entries_and_resolves_late(self):
  sim,cards=self.fixture(['Cloudspire Coordinator','Untethered Express','Brightfield Glider'])
  cloud=cards['Cloudspire Coordinator'];item=next(p for p in sim.players[0].battlefield if p.card.id==cloud.id)
  with self.assertRaises(ValueError):sim.activate_history(0,cloud.id)
  item.fresh=False;sim.activate_history(0,cloud.id)
  both=self.token(sim,'both',subtypes=('Mount','Vehicle'))
  sim.send_to_destination(sim.players[0],item);self.drain(sim)
  pilots=[p for p in sim.players[0].battlefield if p.card.event_definition and p.card.event_definition.pilot_bonus]
  self.assertEqual(len(pilots),3);self.assertTrue(all(p.card.power==1 and p.card.event_definition.pilot_bonus==2 for p in pilots))
  sim.turn+=1;self.assertEqual(sim.history_count(0,('Mount','Vehicle')),0);sim.invariant()
 def test_pilot_bonus_counts_for_crew_and_saddle_not_stats_or_station(self):
  sim,cards=self.fixture(['Cloudspire Coordinator','Untethered Express','Brightfield Glider','Lumen-Class Frigate'])
  item=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id);item.fresh=False
  sim.activate_history(0,item.card.id);self.drain(sim)
  pilots=[p for p in sim.players[0].battlefield if p.card.event_definition and p.card.event_definition.pilot_bonus]
  raw=dict(name='Vehicle',types=['Artifact'],subTypes=['Vehicle'],manaCost='{0}',power='4',toughness='4',oracleText='Crew 3')
  vehicle=s.import_diagnostic_card(self.rules,raw,0,'vehicle',set());sim.enter_creature(replace(vehicle,is_token=True),sim.players[0])
  game=sim.event_game('main');game.crew('vehicle',[pilots[0].card.id],0);sim.sync_events(game)
  self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id=='vehicle').animated)
  self.assertEqual(sim.effective_card(pilots[1]).power,1)
  sim.activate_station(0,cards['Lumen-Class Frigate'].id,pilots[1].card.id);self.drain(sim)
  self.assertEqual(next(p for p in sim.players[0].battlefield if p.card.id==cards['Lumen-Class Frigate'].id).charge_counters,1)
 def test_station_thresholds_summoning_sickness_and_separate_counters(self):
  sim,cards=self.fixture(['Lumen-Class Frigate','Cloudspire Coordinator'])
  frigate=next(p for p in sim.players[0].battlefield if p.card.id==cards['Lumen-Class Frigate'].id)
  cloud=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id)
  sim.activate_station(0,frigate.card.id,cloud.card.id)
  self.assertEqual(frigate.charge_counters,0);self.drain(sim)
  self.assertEqual(frigate.charge_counters,3);self.assertIsNone(sim.effective_card(frigate))
  self.assertEqual(sim.effective_card(cloud).power,4)
  helper=self.token(sim,'helper',power=10,toughness=10);sim.activate_station(0,frigate.card.id,helper.card.id);self.drain(sim)
  self.assertEqual(frigate.charge_counters,14)
  self.assertEqual((sim.effective_card(frigate).power,sim.effective_card(frigate).toughness),(3,5))
  self.assertIn('flying',sim.effective_card(frigate).traits);self.assertIn('lifelink',sim.effective_card(frigate).traits)
  self.assertNotIn(frigate,self.attackable_safe(sim))
 def attackable_safe(self,sim):return sim.attackable(0)
 def test_station_uses_current_or_last_known_power_and_requires_sorcery_timing(self):
  sim,cards=self.fixture(['Lumen-Class Frigate']);frigate=cards['Lumen-Class Frigate'];helper=self.token(sim,'helper',power=3,toughness=3)
  sim.phase='attack'
  with self.assertRaises(ValueError):sim.activate_station(0,frigate.id,'helper')
  sim.phase='main';sim.activate_station(0,frigate.id,'helper');helper.counters=2
  sim.send_to_destination(sim.players[0],helper);self.drain(sim)
  self.assertEqual(next(p for p in sim.players[0].battlefield if p.card.id==frigate.id).charge_counters,5)
 def test_ephemerate_blinks_new_object_resets_state_and_rebounds_once(self):
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);spell=cards['Ephemerate'];target=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id)
  target.counters=3;target.marked_damage=1;target.fresh=False;old_id=target.card.id
  sim.cast_spell(0,spell,target=old_id);self.drain(sim)
  returned=next(p for p in sim.players[0].battlefield if root(p.card)==old_id)
  self.assertNotEqual(returned.card.id,old_id);self.assertEqual((returned.counters,returned.marked_damage),(0,0));self.assertTrue(returned.fresh)
  self.assertIn(spell,sim.players[0].exile);self.assertEqual(len(sim.rebound_pending),1)
  sim.active=1;sim.turn=1;sim.phase='end';sim.step();sim.step();self.drain(sim)
  self.assertIn(spell,sim.players[0].graveyard);self.assertNotIn(spell,sim.players[0].exile)
  self.assertFalse(sim.rebound_pending);self.assertEqual(sum(e['kind']=='blink' for e in sim.events),2)
  sim.invariant();json.dumps(sim.report())
 def test_old_targets_fail_after_blink_and_countered_blink_does_not_rebound(self):
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);spell=cards['Ephemerate'];target=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id)
  sim.cast_spell(0,spell,target=target.card.id);sim.blink_permanent(0,target);self.drain(sim)
  self.assertIn(spell,sim.players[0].graveyard);self.assertFalse(sim.rebound_pending);sim.invariant()
 def test_blink_tokens_do_not_return_and_no_target_rebound_stays_exiled(self):
  sim,cards=self.fixture(['Ephemerate']);token=self.token(sim,'token');spell=cards['Ephemerate']
  sim.cast_spell(0,spell,target='token');self.drain(sim)
  self.assertNotIn(token,sim.players[0].battlefield);self.assertIn(spell,sim.players[0].exile)
  sim.active=1;sim.turn=1;sim.phase='end';sim.step();sim.step();self.drain(sim)
  self.assertIn(spell,sim.players[0].exile);self.assertFalse(sim.rebound_pending);sim.invariant()
 def test_blink_returns_to_owner_and_keeps_physical_card_conservation(self):
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);target=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id)
  sim.players[0].battlefield.remove(target);sim.players[1].battlefield.append(target);sim.invariant()
  sim.blink_permanent(1,target)
  self.assertTrue(any(root(p.card)==target.card.id for p in sim.players[0].battlefield));sim.invariant()

 def test_station_blink_resets_charge_and_old_ability_cannot_charge_new_object(self):
  sim,cards=self.fixture(['Lumen-Class Frigate','Ephemerate']);frigate=next(p for p in sim.players[0].battlefield if p.card.id==cards['Lumen-Class Frigate'].id)
  frigate.charge_counters=12;self.token(sim,'operator',power=4,toughness=4)
  sim.activate_station(0,frigate.card.id,'operator')
  sim.cast_spell(0,cards['Ephemerate'],target=frigate.card.id);self.drain(sim)
  returned=next(p for p in sim.players[0].battlefield if root(p.card)==frigate.card.id)
  self.assertNotEqual(returned.card.id,frigate.card.id);self.assertEqual(returned.charge_counters,0)
  self.assertIsNone(sim.effective_card(returned));sim.invariant()
 def test_crew_effect_waits_on_stack_and_defenders_can_crew_before_blocks(self):
  sim,cards=self.fixture(['Untethered Express']);vehicle=next(p for p in sim.players[0].battlefield if p.card.id==cards['Untethered Express'].id)
  helper=self.token(sim,'pilot',power=1,toughness=1);sim.active=1;sim.stack.active=1;sim.stack.priority=0;sim.phase='block'
  sim.activate_transport(0,'crew',vehicle.card.id,['pilot'])
  self.assertTrue(helper.tapped);self.assertFalse(vehicle.animated)
  self.drain(sim);self.assertTrue(vehicle.animated)
  sim.active=1;sim.stack.priority=1;sim.phase='attack';attacker=self.token(sim,'enemy',1)
  sim.declare_attackers(['enemy']);self.drain(sim)
  self.assertTrue(any(action.kind=='group_blocks' and any(vehicle.card.id in bs for _,bs in action.blocks) for action in sim.legal(0)))
 def test_saddle_uses_pilot_bonus_as_though_power_not_combat_power(self):
  sim,cards=self.fixture(['Cloudspire Coordinator','Brightfield Glider','Untethered Express']);cloud=next(p for p in sim.players[0].battlefield if p.card.id==cards['Cloudspire Coordinator'].id);cloud.fresh=False
  sim.activate_history(0,cloud.card.id);self.drain(sim)
  pilot=next(p for p in sim.players[0].battlefield if p.card.event_definition and p.card.event_definition.pilot_bonus)
  raw=dict(name='Mount',types=['Creature'],subTypes=['Mount'],manaCost='{0}',power='2',toughness='2',oracleText='Saddle 3')
  mount=s.import_diagnostic_card(self.rules,raw,0,'mount',set());sim.enter_creature(replace(mount,is_token=True),sim.players[0])
  sim.activate_transport(0,'saddle','mount',[pilot.card.id]);self.drain(sim)
  item=next(p for p in sim.players[0].battlefield if p.card.id=='mount')
  self.assertTrue(item.saddled);self.assertEqual(sim.effective_card(pilot).power,1)
 def test_countering_ephemerate_or_rebound_leaves_no_illegal_recasts(self):
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);spell=cards['Ephemerate'];target=cards['Cloudspire Coordinator']
  sim.cast_spell(0,spell,target=target.id);sim.counter_stack_item(sim.stack.items[-1]);self.drain(sim)
  self.assertIn(spell,sim.players[0].graveyard);self.assertFalse(sim.rebound_pending)
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);spell=cards['Ephemerate']
  sim.cast_spell(0,spell,target=cards['Cloudspire Coordinator'].id);self.drain(sim)
  sim.active=1;sim.turn=1;sim.phase='end';sim.step();sim.step()
  rebound=next(frame for frame in sim.stack.items if frame.payload[0].get('operation')=='rebound');sim.counter_stack_item(rebound);self.drain(sim)
  self.assertIn(spell,sim.players[0].exile);self.assertFalse(sim.rebound_pending);sim.invariant()
 def test_protection_forces_illegal_colored_aura_off_existing_host(self):
  sim,_=self.fixture([]);host=self.token(sim,'host')
  raw=dict(name='Black blessing',types=['Enchantment'],subTypes=['Aura'],manaCost='{B}',colors=['Black'],oracleText='Enchant creature\nEnchanted creature has lifelink.')
  aura=s.import_diagnostic_card(self.rules,raw,0,'aura',{'Black'});sim.enter_creature(replace(aura,is_token=True),sim.players[0]);sim.players[0].battlefield[-1].attached_to='host'
  memorial=s.import_diagnostic_card(self.rules,self.lookup["Akroma's Memorial"],0,'memorial',set())
  sim.enter_creature(replace(memorial,is_token=True),sim.players[0]);sim.resolve_entry_triggers([],memorial)
  self.assertFalse(any(p.card.id=='aura' for p in sim.players[0].battlefield));self.assertNotIn('lifelink',sim.effective_card(host).traits)
 def test_old_removal_target_is_not_the_returning_physical_card(self):
  sim,cards=self.fixture(['Ephemerate','Cloudspire Coordinator']);target=cards['Cloudspire Coordinator'];spell=cards['Ephemerate']
  player=sim.players[1];old=player.library.pop();removal=replace(old,kind='removal_spell',removal='destroy',mana_cost='{B}',instant=True,colors=('Black',),event_definition=None)
  player.hand.append(removal);player.mana_pool[2]=1;sim.stack.priority=1
  sim.cast_spell(1,removal,target=target.id)
  sim.stack.priority=0;sim.cast_spell(0,spell,target=target.id);self.drain(sim)
  self.assertTrue(any(root(p.card)==target.id for p in sim.players[0].battlefield));self.assertIn(removal,player.graveyard)
  self.assertTrue(any(e['kind']=='illegal_target' for e in sim.events));sim.invariant()

 def test_blinked_attacker_leaves_combat_but_created_attacker_remains(self):
  sim,cards=self.fixture(['Skyknight Vanguard','Ephemerate']);v=cards['Skyknight Vanguard'];self.ready(sim)
  sim.declare_attackers([v.id]);self.drain(sim)
  sim.cast_spell(0,cards['Ephemerate'],target=v.id);self.drain(sim)
  sim.declare_blockers({});self.damage(sim)
  self.assertEqual(sim.players[1].life,39)
  returned=next(p for p in sim.players[0].battlefield if root(p.card)==v.id)
  self.assertNotEqual(returned.card.id,v.id);self.assertTrue(returned.fresh);sim.invariant()
 def test_duplicate_blocker_assignments_are_rejected_without_changing_combat(self):
  sim,_=self.fixture([]);self.token(sim,'a');self.token(sim,'b');self.token(sim,'blocker',1)
  self.ready(sim);sim.declare_attackers(['a','b'])
  with self.assertRaises(ValueError):sim.declare_blockers({'a':['blocker'],'b':['blocker']})
  self.assertEqual(sim.group_combat['blocks'],{})
