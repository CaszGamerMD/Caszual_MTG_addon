import sys,json,unittest
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import Game,Permanent,parse_card
import simulator as s
class AttackChecks(unittest.TestCase):
 def test_real_mount_temporary_bonus_and_vehicle_counter(self):
  lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
  for name in ('Brightfield Glider','Untethered Express'):
   definition=parse_card(lookup[name]);self.assertTrue(definition.supported)
   g=Game(phase='combat');p=Permanent('a',definition,0,fresh=False,saddled=True,animated=True);g.battlefield[p.id]=p
   before=g.stats(p);g.attack(p.id,1)
   if name=='Brightfield Glider':
    self.assertEqual(g.stats(p),(before[0]+1,before[1]+2));self.assertTrue(g.has(p,'flying'))
    g.cleanup();self.assertEqual(g.stats(p),before);self.assertFalse(g.has(p,'flying'))
   else:
    self.assertEqual(p.counters,1);g.cleanup();p.animated=True;self.assertEqual(g.stats(p),(before[0]+1,before[1]+1))
 def test_unfamiliar_mount_condition_and_simulator_roundtrip(self):
  raw=dict(name='Unknown mount',types=['Creature'],subTypes=['Mount'],power='2',toughness='3',manaCost='{G}',oracleText='Vigilance\nWhenever this creature attacks while saddled, it gets +2/+4 and gains flying until end of turn.\nSaddle 2')
  with s.RulesBridge() as rules:
   card=s.import_diagnostic_card(rules,raw,0,'mount',{'Green'});self.assertEqual(card.kind,'creature')
   sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True);owner=sim.players[0]
   (owner.hand if card in owner.hand else owner.library).remove(card);sim.enter_creature(card,owner)
   p=owner.battlefield[0];p.fresh=False
   g=sim.event_game('combat');g.attack(card.id,1);self.assertEqual(g.stats(g.battlefield[card.id]),(2,3))
   p.saddled=True;g=sim.event_game('combat');g.attack(card.id,1);sim.sync_events(g)
   self.assertEqual(sim.effective_card(p).power,4);self.assertIn('flying',sim.effective_card(p).traits)
   g=sim.event_game('cleanup');g.cleanup();sim.sync_events(g);self.assertEqual(sim.effective_card(p).toughness,3)
   sim.invariant()
  raw['oracleText']+='\nDraw a card.'
  self.assertFalse(parse_card(raw).supported)
 def test_saddled_treasure_attack_real_and_unseen_full_rules(self):
  lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
  real=lookup['Gilded Ghoda']
  with s.RulesBridge() as rules:
   for raw,expected in ((real,1),(dict(real,name='Unknown Mount',oracleText='Whenever this creature attacks while saddled, create three Treasure tokens.\nSaddle 1'),3)):
    card=s.import_diagnostic_card(rules,raw,0,'ghoda-'+raw['name'],{'White'})
    self.assertEqual(card.kind,'creature')
    self.assertEqual(card.event_definition.attack_effects[0][:2],('saddled_treasures',expected))
    sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
    owner=sim.players[0]
    (owner.hand if card in owner.hand else owner.library).remove(card)
    sim.enter_creature(card,owner)
    mount=next(p for p in owner.battlefield if p.card.id==card.id)
    mount.fresh=False
    g=sim.event_game('combat');g.attack(card.id,1,defer=True)
    self.assertFalse(any(e.get('operation')=='create_treasures' for e in g.events))
    mount.saddled=True
    g=sim.event_game('combat');g.attack(card.id,1,defer=True)
    events=[e for e in g.events if e.get('operation')=='create_treasures']
    self.assertEqual(len(events),1)
    self.assertEqual(events[0]['amount'],expected)
    before=sum(p.card.name=='Treasure' for p in owner.battlefield)
    sim.resolve_entry_triggers(events,card)
    self.assertEqual(sum(p.card.name=='Treasure' for p in owner.battlefield),before+expected)
    self.assertTrue(all(p.card.is_token for p in owner.battlefield if p.card.name=='Treasure'))
    sim.invariant()
   bad=dict(real,oracleText=real['oracleText']+'\nWhenever this creature attacks, win the game.')
   self.assertEqual(s.import_diagnostic_card(rules,bad,0,'bad',{'White'}).kind,'unsupported')
   wrong=dict(real,subTypes=['Horse'])
   self.assertEqual(s.import_diagnostic_card(rules,wrong,0,'wrong',{'White'}).kind,'unsupported')
 def test_attack_subtype_drain_counts_other_creatures_once_at_resolution(self):
  lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
  real=lookup['Valley Rotcaller']
  with s.RulesBridge() as rules:
   for raw in (real,dict(real,name='Unknown Caller',oracleText='Menace\nWhenever this creature attacks, each opponent loses X life and you gain X life, where X is the number of other Elves, Goblins, and Faeries you control.')):
    card=s.import_diagnostic_card(rules,raw,0,'caller-'+raw['name'],{'Black','Green'})
    self.assertEqual(card.kind,'creature')
    self.assertEqual(card.event_definition.attack_effects[0][0],'attack_subtype_drain')
    types=card.event_definition.attack_effects[0][3]
    def creature(uid,name,subtypes):
     definition=s.EventDefinition(name,frozenset({'Creature'}),frozenset(subtypes),False,2,2,frozenset())
     return s.Card(uid,name,'creature',power=2,toughness=2,traits='2;2;',land_subtypes=subtypes,event_definition=definition)
    both=creature('both','Both types',(types[0],types[1]))
    other=creature('other','Other type',(types[-1],))
    enemy=creature('enemy','Enemy type',(types[0],))
    sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card,both,other],s.demo_deck(1)+[enemy]),diagnostic=True)
    owner=sim.players[0]
    for creature_card,player in ((card,owner),(both,owner),(other,owner),(enemy,sim.players[1])):
     (player.hand if creature_card in player.hand else player.library).remove(creature_card)
     sim.enter_creature(creature_card,player)
    mount=next(p for p in owner.battlefield if p.card.id==card.id);mount.fresh=False
    g=sim.event_game('combat');g.attack(card.id,1,defer=True)
    events=[e for e in g.events if e.get('operation')=='attack_subtype_drain']
    self.assertEqual(len(events),1)
    sim.send_to_destination(owner,mount)
    before=(owner.life,sim.players[1].life)
    sim.resolve_entry_triggers(events,card)
    self.assertEqual((owner.life,sim.players[1].life),(before[0]+2,before[1]-2))
    sim.invariant()
   bad=dict(real,oracleText=real['oracleText']+'\nCreate a mystery token.')
   self.assertEqual(s.import_diagnostic_card(rules,bad,0,'bad-caller',{'Black'}).kind,'unsupported')
   repeated=dict(real,oracleText='Menace\nWhenever this creature attacks, each opponent loses X life and you gain X life, where X is the number of other Squirrels, Squirrels, and Rats you control.')
   self.assertEqual(s.import_diagnostic_card(rules,repeated,0,'repeated',{'Black'}).kind,'unsupported')
 def test_generic_subtype_combat_damage_discard(self):
  from unittest.mock import patch
  with s.RulesBridge() as rules:
   raw=dict(name='Unfamiliar watcher',types=['Creature'],subTypes=['Cleric'],power='2',toughness='3',manaCost='{B}',oracleText='Whenever a Goblin deals combat damage to a player, that player discards a card.')
   watcher=s.import_diagnostic_card(rules,raw,0,'watcher',{'Black'});self.assertEqual(watcher.kind,'creature')
   attacker=s.Card('goblin','Unknown Goblin','creature',mana_cost='{R}',traits='1;1;',power=1,toughness=1,land_subtypes=('Goblin',))
   sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[watcher,attacker],s.demo_deck(1)),diagnostic=True)
   p=sim.players[0]
   for c in (watcher,attacker):
    (p.hand if c in p.hand else p.library).remove(c);sim.enter_creature(c,p)
   before=len(sim.players[1].hand);sim.phase='block';sim.pending=attacker.id
   with patch.object(sim,'decide',return_value=s.Candidate('take','block')):sim.step()
   self.assertEqual(len(sim.players[1].hand),before-1)
   self.assertEqual(len(sim.players[1].graveyard),1)
   sim.invariant()
   before=len(sim.players[1].hand);sim.phase='block';sim.pending=attacker.id
   result=sim.damage(attacker,None);result['damage']=0
   with patch.object(sim,'decide',return_value=s.Candidate('take','block')),patch.object(sim,'damage',return_value=result):sim.step()
   self.assertEqual(len(sim.players[1].hand),before)
