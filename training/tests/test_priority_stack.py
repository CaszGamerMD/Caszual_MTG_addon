import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from priority_stack import PriorityStack
import simulator as s

class StackChecks(unittest.TestCase):
 def test_lifo_two_passes_priority_reset_and_counter(self):
  st=PriorityStack();a=st.push(0,'a','A',actor=0)
  self.assertEqual(st.pass_priority(0)[0],'pass')
  with self.assertRaises(ValueError):st.pass_priority(0)
  b=st.push(1,'b','B',actor=1)
  self.assertEqual(st.passes,0)
  st.pass_priority(1);status,item=st.pass_priority(0)
  self.assertEqual((status,item.id),('resolve',b.id));self.assertEqual(st.priority,0)
  self.assertEqual(st.counter(a.id),a);self.assertIsNone(st.counter(a.id))
  st.pass_priority(0);self.assertEqual(st.pass_priority(1)[0],'advance')
 def test_krenko_waits_for_passes_and_uses_last_known_power(self):
  raw=next(c for c in json.loads((Path(__file__).resolve().parents[1]/'decks/5254666-garbo-gobbos.json').read_text())['mainboard'] if c['name']=='Krenko, Tin Street Kingpin')
  with s.RulesBridge() as rules:
   card=s.import_diagnostic_card(rules,raw,0,'source',{'Red'})
   sim=s.Simulator(rules,42,decks=(s.demo_deck(0)+[card],s.demo_deck(1)),diagnostic=True)
   p=sim.players[0];(p.hand if card in p.hand else p.library).remove(card);sim.enter_creature(card,p)
   source=p.battlefield[0];source.fresh=False
   game=sim.event_game('combat');game.attack(card.id,1,defer=True);sim.sync_events(game)
   sim.manual_priority=True
   sim.resolve_entry_triggers([e for e in game.events if e['kind']=='trigger'],card)
   self.assertEqual(source.counters,0);self.assertEqual(len(p.battlefield),1)
   sim.pass_priority(0);self.assertEqual(len(p.battlefield),1)
   source.counters=3
   sim.send_to_destination(p,source)
   sim.pass_priority(1)
   self.assertEqual(len(p.battlefield),4) # Last power 4; no counter on departed source.
   self.assertTrue(all(x.card.is_token for x in p.battlefield))
   self.assertEqual(sim.stack.priority,0);sim.invariant()
 def test_apnap_order_and_no_private_payload_in_public_stack(self):
  with s.RulesBridge() as rules:
   sim=s.Simulator(rules,42,diagnostic=True);sim.manual_priority=True
   card=s.Card('test','Source','creature')
   events=[dict(operation='lose_life',amount=1,gain=0,controller=i,name=str(i)) for i in (0,1)]
   sim.resolve_entry_triggers(events,card)
   self.assertEqual([x['controller'] for x in sim.stack.public()],[0,1])
   self.assertNotIn('payload',str(sim.stack.public()))
   sim.pass_priority(0);sim.pass_priority(1)
   self.assertEqual([p.life for p in sim.players],[39,40])
   self.assertEqual(len(sim.stack.items),1)
