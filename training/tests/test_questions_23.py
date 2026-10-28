import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from card_events import Game,Permanent

class QuestionChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge()
  cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls): cls.rules.close()
 def test_color_anthem_and_basic_count_land(self):
  anthem=s.import_diagnostic_card(self.rules,self.lookup['Honor of the Pure'],0,'anthem',{'White'})
  self.assertEqual(anthem.kind,'enchantment')
  g=Game();g.enter(Permanent('anthem',anthem.event_definition,0))
  from dataclasses import replace
  for ident,color,seat in [('white','White',0),('red','Red',0),('enemy','White',1)]:
   d=s.EventDefinition(ident,frozenset({'Creature'}),frozenset(),False,1,1,frozenset(),colors=frozenset({color}))
   g.enter(Permanent(ident,d,seat))
  self.assertEqual([g.stats(g.battlefield[i]) for i in ['white','red','enemy']],[(2,2),(1,1),(1,1)])
  land=s.import_diagnostic_card(self.rules,self.lookup['Radiant Summit'],0,'summit',{'White','Red'})
  self.assertEqual((land.kind,land.mask),('land',9))
  basic=s.Card('b','Basic','land',mask=1,basic_land=True)
  self.assertTrue(s.land_enters_tapped(land,[basic]))
  self.assertFalse(s.land_enters_tapped(land,[basic,replace(basic,id='b2')]))
  self.assertTrue(s.land_enters_tapped(land,[replace(basic,basic_land=False)]*3))
 def test_storm_counts_casts_not_copies_and_resets_by_turn(self):
  raw=self.lookup['Empty the Warrens']
  cards=[s.import_diagnostic_card(self.rules,raw,0,'storm'+str(i),{'Red'}) for i in range(2)]
  opener=s.import_diagnostic_card(self.rules,dict(name='Unknown opener',types=['Sorcery'],manaCost='{0}',oracleText='Create two 1/1 red Goblin creature tokens.'),0,'opener',{'Red'})
  lands=[s.Card('r'+str(i),'Mountain','land',mask=8) for i in range(8)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+cards+[opener]+lands,s.demo_deck(1)),diagnostic=True);p=sim.players[0]
  for c in cards+[opener]+lands: (p.hand if c in p.hand else p.library).remove(c)
  p.hand.extend([opener]+cards);p.battlefield.extend(s.Permanent(c) for c in lands);sim.phase='main'
  sim.log('cast','Previous turn spell',card='old');sim.turn+=1
  sim.log('land','Land play does not count')
  for c in [opener]+cards:
   self.assertEqual(c.kind,'token_spell')
   with patch.object(sim,'decide',return_value=s.Candidate(c.id,'cast',card_id=c.id)):sim.step()
  self.assertEqual([e['details']['copies'] for e in sim.events if e['kind']=='storm'],[1,2])
  self.assertEqual(sum(p.card.is_token for p in p.battlefield),12)
  self.assertEqual(sum(e['kind']=='spell_copy' for e in sim.events),3)
  self.assertEqual(len(p.graveyard),3)
  sim.invariant()
