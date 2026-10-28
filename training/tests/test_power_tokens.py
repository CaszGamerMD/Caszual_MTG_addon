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
