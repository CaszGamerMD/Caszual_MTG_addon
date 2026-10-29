import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
class AttachmentChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self,name):
  card=s.import_diagnostic_card(self.rules,self.lookup[name],0,'attachment',{'White','Black'})
  creature=s.Card('creature','Creature','creature',mana_cost='{0}',traits='2;2;',power=2,toughness=2)
  lands=[s.Card('mana'+str(i),'Land','land',mask=63) for i in range(4)]
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[card,creature]+lands,s.demo_deck(1)),diagnostic=True);p=sim.players[0]
  for c in [card,creature]+lands:(p.hand if c in p.hand else p.library).remove(c)
  p.hand.append(card);sim.enter_creature(creature,p);p.battlefield.extend(s.Permanent(c) for c in lands)
  sim.phase='main';return sim,card,p.battlefield[0]
 def test_collar_equip_waits_for_resolution_grants_and_detaches(self):
  sim,card,target=self.fixture('Basilisk Collar');self.assertEqual(card.kind,'equipment')
  sim.cast_spell(0,card);sim.manual_priority=True
  sim.activate_equip(0,card.id,target.card.id)
  self.assertNotIn('deathtouch',sim.effective_card(target).traits)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertIn('deathtouch',sim.effective_card(target).traits);self.assertIn('lifelink',sim.effective_card(target).traits)
  equipment=next(p for p in sim.players[0].battlefield if p.card.id==card.id)
  self.assertEqual(sum(p.tapped for p in sim.players[0].battlefield),3)
  sim.send_to_destination(sim.players[0],target)
  self.assertIn(equipment,sim.players[0].battlefield);self.assertIsNone(equipment.attached_to);sim.invariant()
 def test_aura_target_disappears_and_graveyard_cleanup(self):
  sim,card,target=self.fixture('Lifelink');self.assertEqual(card.kind,'aura')
  sim.cast_spell(0,card,target=target.card.id)
  self.assertIn('lifelink',sim.effective_card(target).traits)
  sim.send_to_destination(sim.players[0],target)
  self.assertIn(card,sim.players[0].graveyard);sim.invariant()
  sim,card,target=self.fixture('Lifelink');sim.manual_priority=True
  sim.cast_spell(0,card,target=target.card.id)
  sim.send_to_destination(sim.players[0],target)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertIn(card,sim.players[0].graveyard);sim.invariant()
 def test_full_text_rejection(self):
  raw=dict(self.lookup['Basilisk Collar'],name='Unknown equipment')
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'White'}).kind,'equipment')
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'White'}).kind,'unsupported')
