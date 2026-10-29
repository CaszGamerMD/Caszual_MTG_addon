"""Equipment, temporary opposing ability loss, timestamps and hexproof targeting."""
import sys,json,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import Game,Permanent,parse_card
class ShadowspearChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.raw=next(c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard'] if c['name']=='Shadowspear')
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self):
  spear=s.import_diagnostic_card(self.rules,self.raw,0,'spear',{'Black'})
  self.assertEqual(spear.kind,'equipment')
  removal=s.import_diagnostic_card(self.rules,dict(name='Removal',types=['Instant'],manaCost='{B}',oracleText='Destroy target creature.'),0,'removal',{'Black'})
  lands=[s.Card('land'+str(i),'Mana','land',mask=63) for i in range(8)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[spear,removal]+lands,s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for card in [spear,removal]+lands:(p.hand if card in p.hand else p.library).remove(card)
  p.hand.extend([spear,removal]);p.battlefield.extend(s.Permanent(card) for card in lands)
  self.token(sim,'host',0,())
  enemy=self.token(sim,'protected',1,('hexproof','indestructible'))
  sim.phase='main';sim.manual_priority=True
  sim.cast_spell(0,spear);self.resolve(sim)
  return sim,spear,enemy,removal
 def token(self,sim,identifier,seat,abilities):
  definition=s.EventDefinition(identifier,frozenset({'Creature'}),frozenset(),False,2,2,frozenset(abilities))
  card=s.Card(identifier,identifier,'creature','{0}','2;2;',2,2,event_definition=definition,is_token=True)
  sim.enter_creature(card,sim.players[seat]);return sim.players[seat].battlefield[-1]
 def resolve(self,sim):sim.pass_priority(sim.stack.priority);sim.pass_priority(sim.stack.priority)
 def test_equipment_stats_keywords_and_removal_unattached(self):
  sim,spear,enemy,removal=self.fixture()
  sim.activate_equip(0,spear.id,'host');self.resolve(sim)
  host=next(p for p in sim.players[0].battlefield if p.card.id=='host')
  self.assertEqual((sim.effective_card(host).power,sim.effective_card(host).toughness),(3,3))
  self.assertIn('lifelink',sim.effective_card(host).traits);self.assertIn('trample',sim.effective_card(host).traits)
  item=next(p for p in sim.players[0].battlefield if p.card.id==spear.id);item.attached_to=None
  sim.activate_strip(0,spear.id)
  self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[enemy.card.id],'hexproof'))
  self.resolve(sim)
  game=sim.event_game('main')
  self.assertFalse(game.has(game.battlefield[enemy.card.id],'hexproof'))
  self.assertFalse(game.has(game.battlefield[enemy.card.id],'indestructible'))
  self.assertNotIn('indestructible',sim.effective_card(enemy).traits)
  self.assertFalse(sim.players[0].battlefield[0].lost_abilities);json.dumps(sim.report());sim.invariant()
 def test_hexproof_blocks_enemy_targeting_until_strip_resolves(self):
  sim,spear,enemy,removal=self.fixture()
  self.assertNotIn(enemy.card.id,{p.card.id for _,p in sim.creature_targets(0)})
  self.assertIn(enemy.card.id,{p.card.id for _,p in sim.creature_targets(1)})
  with self.assertRaises(ValueError):sim.cast_spell(0,removal,target=enemy.card.id)
  sim.activate_strip(0,spear.id);self.resolve(sim)
  sim.cast_spell(0,removal,target=enemy.card.id);self.resolve(sim)
  self.assertNotIn(enemy,sim.players[1].battlefield);sim.invariant()
 def test_hexproof_gained_in_response_invalidates_existing_target(self):
  sim,spear,enemy,removal=self.fixture();sim.activate_strip(0,spear.id);self.resolve(sim)
  sim.cast_spell(0,removal,target=enemy.card.id)
  game=sim.event_game('main');game.grant_temporary(game.battlefield[enemy.card.id],'hexproof');sim.sync_events(game)
  self.resolve(sim)
  self.assertIn(enemy,sim.players[1].battlefield)
  self.assertIn(removal,sim.players[0].graveyard)
 def test_new_permanents_and_later_grants_survive_earlier_loss(self):
  sim,spear,enemy,removal=self.fixture();sim.activate_strip(0,spear.id);self.resolve(sim)
  newer=self.token(sim,'later',1,('hexproof','indestructible'))
  game=sim.event_game('main')
  self.assertTrue(game.has(game.battlefield[newer.card.id],'hexproof'))
  self.assertFalse(game.has(game.battlefield[enemy.card.id],'hexproof'))
  game.grant_temporary(game.battlefield[enemy.card.id],'hexproof');sim.sync_events(game)
  self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[enemy.card.id],'hexproof'))
  sim.activate_strip(0,spear.id);self.resolve(sim)
  game=sim.event_game('main');self.assertFalse(game.has(game.battlefield[enemy.card.id],'hexproof'))
  self.assertFalse(game.has(game.battlefield[newer.card.id],'indestructible'));sim.invariant()
 def test_static_grants_are_ordered_and_cleanup_restores_printed_abilities(self):
  sim,spear,enemy,removal=self.fixture()
  raw=dict(name='Guardian',types=['Enchantment'],oracleText='Creatures you control have indestructible.')
  definition=parse_card(raw)
  grant=s.Card('grant','Guardian','enchantment',event_definition=definition,is_token=True)
  sim.enter_creature(grant,sim.players[1])
  sim.activate_strip(0,spear.id);self.resolve(sim)
  game=sim.event_game('main');self.assertFalse(game.has(game.battlefield[enemy.card.id],'indestructible'))
  sim.enter_creature(replace(grant,id='new-grant'),sim.players[1])
  game=sim.event_game('main');self.assertTrue(game.has(game.battlefield[enemy.card.id],'indestructible'))
  sim.phase='cleanup';sim.step()
  game=sim.event_game('main');self.assertTrue(game.has(game.battlefield[enemy.card.id],'hexproof'))
  self.assertFalse(enemy.lost_abilities);self.assertFalse(enemy.temporary_ability_times)
 def test_source_departure_does_not_cancel_and_losing_indestructible_checks_damage(self):
  sim,spear,enemy,removal=self.fixture();enemy.marked_damage=2
  sim.activate_strip(0,spear.id)
  sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield if p.card.id==spear.id))
  self.resolve(sim)
  self.assertNotIn(enemy,sim.players[1].battlefield);sim.invariant()
 def test_attachment_grants_receive_a_new_timestamp_when_changed(self):
  target=parse_card(dict(name='Host',types=['Creature'],power='2',toughness='2',oracleText=''))
  attachment=parse_card(dict(name='Armor',types=['Artifact'],subTypes=['Equipment'],oracleText='Equipped creature has indestructible.\nEquip {0}'))
  game=Game();host=Permanent('host',target,1);armor=Permanent('armor',attachment,1,attached_to='host')
  game.enter_batch([host,armor]);game.lose_opposing_abilities(0,{'indestructible'})
  self.assertFalse(game.has(host,'indestructible'))
  armor.attached_to=None;armor.attached_to='host';armor.attachment_at=game.timestamp()
  self.assertTrue(game.has(host,'indestructible'))
 def test_unfamiliar_text_and_unsupported_remainder(self):
  raw=dict(self.raw,name='Unknown tool',oracleText='Equipped creature gets +2/+3 and has lifelink.\n{2}{B}: Permanents your opponents control lose indestructible until end of turn.\nEquip {1}')
  card=s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Black'})
  self.assertEqual(card.kind,'equipment');self.assertEqual(card.event_definition.ability_removals[0][0],'{2}{B}')
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'unknown',{'Black'}).kind,'unsupported')
  raw=dict(name='Unknown shield',types=['Creature'],manaCost='{G}',power='2',toughness='2',oracleText='Hexproof')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'shield',{'Green'}).kind,'creature')
