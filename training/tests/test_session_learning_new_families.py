"""Regression: generalized colored ETB, Treasure death, charge Equipment."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s

class NewOracleFamilies(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge();cls.lookup={}
  for path in (Path(__file__).resolve().parents[1]/'decks').glob('*.json'):
   deck=json.loads(path.read_text())
   cls.lookup.update({c['name']:c for c in deck['mainboard']})
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def card(self,name,text,uid='new'):
  return s.import_diagnostic_card(self.rules,dict(name=name,oracleText=text,
   types=['Creature'],subTypes=['Elf'],colors=['Green'],manaCost='{1}{G}',
   power='2',toughness='2'),0,uid,{'Green','Black','Blue'})
 def drain(self,sim):
  sim.manual_priority=False
  with patch.object(s.Policy,'choose',side_effect=lambda obs:next(x for x in obs.legal_actions if x.kind=='priority_pass')):
   sim.drain_priority()
 def test_colored_entry_targets_and_stack(self):
  source=s.import_diagnostic_card(self.rules,self.lookup['Ivy Lane Denizen'],0,'ivy',{'Green'})
  self.assertNotEqual(source.kind,'unsupported')
  clause='Whenever another blue creature you control enters, put two +1/+1 counters on target creature.'
  unseen=self.card('Unseen Gardener',clause)
  self.assertEqual(unseen.event_definition.triggers[0].effect.amount,2)
  self.assertEqual(unseen.event_definition.triggers[0].subject.color,'Blue')
  self.assertEqual(self.card('Unknown',clause+'\nWin the game.').kind,'unsupported')
  ally=self.card('Ally','',uid='ally')
  sim=s.Simulator(self.rules,13,decks=(s.demo_deck(0)+[source,ally],s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for c in (source,ally):(p.hand if c in p.hand else p.library).remove(c)
  p.battlefield.append(s.Permanent(source,fresh=False))
  sim.active=0;sim.phase='main';sim.stack.priority=0;sim.manual_priority=True
  sim.resolve_entry_triggers(sim.enter_creature(ally,p),ally)
  self.assertEqual(next(x for x in p.battlefield if x.card.id=='ally').counters,0)
  self.drain(sim)
  self.assertEqual(next(x for x in p.battlefield if x.card.id=='ally').counters,1)
  sim.invariant()
 def test_death_treasure_is_not_immediate(self):
  source=s.import_diagnostic_card(self.rules,self.lookup['Pitiless Plunderer'],0,'pit',{'Black'})
  self.assertNotEqual(source.kind,'unsupported')
  clause='Whenever another creature you control dies, create three Treasure tokens.'
  self.assertEqual(self.card('Unseen Broker',clause).event_definition.triggers[0].effect.amount,3)
  self.assertEqual(self.card('Unknown',clause+'\nUnknown action.').kind,'unsupported')
  ally=self.card('Ally','',uid='ally')
  sim=s.Simulator(self.rules,14,decks=(s.demo_deck(0)+[source,ally],s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for c in (source,ally):
   (p.hand if c in p.hand else p.library).remove(c);p.battlefield.append(s.Permanent(c,fresh=False))
  sim.active=0;sim.phase='main';sim.stack.priority=0;sim.manual_priority=True
  sim.destroy_batch(((0,next(x for x in p.battlefield if x.card.id=='ally')),),source)
  self.assertFalse(any(x.card.name=='Treasure' for x in p.battlefield))
  self.drain(sim)
  self.assertEqual(sum(x.card.name=='Treasure' for x in p.battlefield),1)
  sim.invariant()
 def test_charge_equipment_counts_source_not_host(self):
  source=s.import_diagnostic_card(self.rules,self.lookup['Excalibur II'],0,'eq',{'Blue','Black'})
  self.assertEqual(source.kind,'equipment')
  raw=dict(self.lookup['Excalibur II'],name='Unseen Charged Sword',
   oracleText=self.lookup['Excalibur II']['oracleText'].replace('Excalibur II','Unseen Charged Sword').replace('+1/+1 for each charge','+2/+3 for each charge'))
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'renamed',{'Blue','Black'}).event_definition.equipment_charge_scale,(2,3))
  self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,oracleText=raw['oracleText']+'\nWin the game.'),0,'bad',{'Blue','Black'}).kind,'unsupported')
  host=self.card('Host','',uid='host')
  sim=s.Simulator(self.rules,15,decks=(s.demo_deck(0)+[source,host],s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for c in (source,host):
   (p.hand if c in p.hand else p.library).remove(c);p.battlefield.append(s.Permanent(c,fresh=False))
  equipment=next(x for x in p.battlefield if x.card.id=='eq');equipment.attached_to='host'
  sim.active=0;sim.phase='main';sim.stack.priority=0;sim.manual_priority=True
  sim.gain_life(0,5);sim.resolve_entry_triggers([],source)
  self.assertEqual(equipment.charge_counters,0)
  self.drain(sim)
  self.assertEqual(equipment.charge_counters,1)
  self.assertEqual(sim.effective_card(next(x for x in p.battlefield if x.card.id=='host')).power,3)
  sim.invariant()
if __name__=='__main__':unittest.main()
