import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class SweepChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge()
  cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def test_real_sweep_simultaneous_deaths_and_exemptions(self):
  spell=s.import_diagnostic_card(self.rules,self.lookup['Ruinous Ultimatum'],0,'sweep',{'White','Red','Black'})
  self.assertEqual(spell.kind,'removal_spell')
  enemies=[s.import_diagnostic_card(self.rules,self.lookup[name],1,'enemy'+str(i),{'White','Red','Black','Green'})
           for i,name in enumerate(['Blood Artist','Nested Shambler','Glorious Anthem','Sol Ring'])]
  lands=[s.Card('mana'+str(i),'Land','land',mask=mask) for i,mask in enumerate([8,8,1,1,1,4,4])]
  ally=s.Card('ally','Ally','creature',mana_cost='{0}',traits='1;1;',power=1,toughness=1)
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[spell,ally]+lands,s.demo_deck(1)+enemies),diagnostic=True)
  for seat,cards in [(0,[spell,ally]+lands),(1,enemies)]:
   p=sim.players[seat]
   for c in cards:(p.hand if c in p.hand else p.library).remove(c)
  sim.players[0].hand.append(spell)
  sim.players[0].battlefield.extend(s.Permanent(c) for c in lands+[ally])
  for c in enemies:
   if c.kind=='mana_artifact':sim.players[1].battlefield.append(s.Permanent(c))
   else:sim.enter_creature(c,sim.players[1])
  for ident,types,abilities in [('forest',{'Land','Creature'},set()),('keeper',{'Creature'},{'indestructible'})]:
   d=s.EventDefinition(ident,frozenset(types),frozenset({'Forest'}),False,1,1,frozenset(abilities))
   c=s.Card(ident,ident,'creature',traits='1;1;',power=1,toughness=1,event_definition=d,is_token=True)
   sim.enter_creature(c,sim.players[1])
  sim.manual_priority=True;sim.phase='main';sim.cast_spell(0,spell)
  self.assertEqual(len(sim.players[1].battlefield),6)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual({p.card.id for p in sim.players[1].battlefield},{'forest','keeper'})
  self.assertEqual({c.id for c in sim.players[1].graveyard},{c.id for c in enemies})
  self.assertEqual([p.life for p in sim.players],[40,40])
  self.assertEqual(len(sim.stack.items),3) # Artist sees two deaths, Shambler sees itself.
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  self.assertEqual([p.life for p in sim.players],[38,42])
  self.assertEqual(len(sim.players[1].battlefield),4) # Shambler had +1/+1 from the dying Anthem.
  self.assertIn(ally,[p.card for p in sim.players[0].battlefield])
  self.assertTrue(all(p.tapped for p in sim.players[0].battlefield if p.card.kind=='land'))
  sim.invariant()
 def test_unfamiliar_name_and_extra_rules(self):
  raw=dict(name='Unknown sweep',types=['Sorcery'],manaCost='{1}',oracleText='Destroy all nonland permanents your opponents control.')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'}).removal,'opponent_nonlands')
  raw['oracleText']+=' Draw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'}).kind,'unsupported')
