import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import parse_card

class PowerTokenChecks(unittest.TestCase):
 def test_real_krenko_counter_precedes_power_and_repeat_attacks(self):
  raw=next(c for c in json.loads((Path(__file__).resolve().parents[1]/'decks/5254666-garbo-gobbos.json').read_text())['mainboard'] if c['name']=='Krenko, Tin Street Kingpin')
  with s.RulesBridge() as rules:
   card=s.import_diagnostic_card(rules,raw,0,'krenko',{'Red'});self.assertEqual(card.kind,'creature')
   sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True);p=sim.players[0]
   (p.hand if card in p.hand else p.library).remove(card);sim.enter_creature(card,p)
   source=p.battlefield[0];source.fresh=False
   for expected,counters in [(2,1),(5,2)]:
    source.tapped=False;sim.phase='attack'
    with patch.object(sim,'decide',return_value=s.Candidate(card.id,'attack',card_id=card.id)):sim.step()
    self.assertEqual(source.counters,counters)
    tokens=[p for p in p.battlefield if p.card.is_token]
    self.assertEqual(len(tokens),expected)
    self.assertTrue(all(p.fresh and not p.tapped for p in tokens))
    self.assertTrue(all(p.card.event_definition.subtypes==frozenset({'Goblin'}) for p in tokens))
    sim.invariant()
 def test_lifegain_counter_then_last_known_death_power_tokens(self):
  raw=next(c for c in json.loads((Path(__file__).resolve().parents[1]/'decks/14850373-budget-deck.json').read_text())['mainboard'] if c['name']=="Elenda's Hierophant")
  with s.RulesBridge() as rules:
   for definition,subtype,bonus in ((raw,'Vampire',1),
       (dict(raw,name='Unseen Pilgrim',oracleText='Flying\nWhenever you gain life, put two +1/+1 counters on this creature.\nWhen this creature dies, create X 2/3 blue Drake creature tokens with flying, where X is its power.'),'Drake',2)):
    card=s.import_diagnostic_card(rules,definition,0,'life-'+definition['name'],{'White','Blue'})
    self.assertEqual(card.kind,'creature')
    self.assertEqual(len(card.event_definition.triggers),2)
    sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
    owner=sim.players[0]
    (owner.hand if card in owner.hand else owner.library).remove(card)
    sim.enter_creature(card,owner)
    source=next(p for p in owner.battlefield if p.card.id==card.id)
    sim.gain_life(0,3)
    sim.resolve_entry_triggers([],card)
    self.assertEqual(source.counters,bonus)
    source.temporary_power=2
    expected=card.power+bonus+2
    sim.destroy_batch([(0,source)],card)
    tokens=[p for p in owner.battlefield if p.card.is_token and p.card.event_definition and subtype in p.card.event_definition.subtypes]
    self.assertEqual(len(tokens),expected)
    self.assertEqual(len([c for c in owner.graveyard if c.id==card.id]),1)
    self.assertTrue(all('lifelink' in p.card.event_definition.abilities for p in tokens) if subtype=='Vampire' else all('flying' in p.card.event_definition.abilities for p in tokens))
    sim.invariant()
   bad=dict(raw,oracleText=raw['oracleText']+'\nWhen this creature dies, win the game.')
   self.assertEqual(s.import_diagnostic_card(rules,bad,0,'bad',{'White'}).kind,'unsupported')
   bad=dict(raw,oracleText=raw['oracleText'].replace('where X is its power','where X is your life total'))
   self.assertEqual(s.import_diagnostic_card(rules,bad,0,'bad2',{'White'}).kind,'unsupported')
 def test_unfamiliar_name_and_characteristics_no_trailing_guess(self):
  raw=dict(name='Unknown summoner',types=['Creature'],power='3',toughness='4',oracleText="Whenever this creature attacks, put a +1/+1 counter on it, then create a number of 2/3 blue Drake creature tokens with flying equal to this creature's power.")
  d=parse_card(raw);self.assertTrue(d.supported)
  from card_events import Game,Permanent
  g=Game(phase='combat');g.battlefield['s']=Permanent('s',d,0,fresh=False,counters=2)
  g.attack('s',1)
  event=next(e for e in g.events if e.get('operation')=='create_tokens')
  self.assertEqual(event['tokenSpec']['amount'],6)
  self.assertEqual(event['tokenSpec']['power'],2)
  self.assertEqual(event['tokenSpec']['keywords'],['flying'])
  raw['oracleText']+=' Draw a card.';self.assertFalse(parse_card(raw).supported)
