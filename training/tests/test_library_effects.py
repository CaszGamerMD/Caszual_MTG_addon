"""Real Muxus and generic reveal/filter plus attack-count programs."""
import json,sys,unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from library_effects import mana_value
class LibraryChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rules=s.RulesBridge()
  cls.lookup={c['name']:c for p in (Path(__file__).resolve().parents[1]/'decks').glob('*.json') for c in json.loads(p.read_text())['mainboard']}
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def card(self,name,uid,**changes):
  raw=dict(self.lookup[name],**changes)
  return s.import_diagnostic_card(self.rules,raw,0,uid,{'Red','Black'})
 def fixture(self,cards):
  muxus=self.card('Muxus, Goblin Grandee','muxus');self.assertEqual(muxus.kind,'creature')
  sim=s.Simulator(self.rules,42,decks=(s.demo_deck(0)+[muxus]+cards,s.demo_deck(1)),diagnostic=True)
  p=sim.players[0]
  for card in [muxus]+cards:(p.hand if card in p.hand else p.library).remove(card)
  p.library.extend(reversed(cards))
  sim.manual_priority=True;sim.phase='main'
  triggers=sim.enter_creature(muxus,p);sim.resolve_entry_triggers(triggers,muxus)
  return sim,muxus
 def test_reveal_filters_printed_types_subtypes_and_mana_value(self):
  goblin=self.card('Goblin Instigator','goblin')
  expensive=self.card('Goblin Instigator','expensive',manaCost='{6}{R}')
  nongoblin=self.card('Goblin Instigator','nongoblin',subTypes=['Elf'])
  artifact=self.card('Basilisk Collar','noncreature',subTypes=['Goblin','Equipment'])
  land=s.Card('land','Mountain','land',mask=8,printed_types=('Land',),printed_mana_value=0)
  sixth=self.card('Goblin Instigator','sixth',manaCost='{4}{R}')
  cards=[goblin,expensive,nongoblin,artifact,land,sixth]
  sim,source=self.fixture(cards);p=sim.players[0];untouched=[c for c in p.library if c not in cards]
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual({p.card.id for p in p.battlefield},{'muxus','goblin','sixth'})
  self.assertEqual(len(sim.stack.items),2)
  self.assertEqual(p.library[4:],untouched)
  self.assertEqual({c.id for c in p.library[:4]},{c.id for c in cards[1:5]})
  self.assertEqual([e['details']['revealed'] for e in sim.events if e['kind']=='reveal'][0],[dict(id=c.id,name=c.name) for c in cards])
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  self.assertEqual(len(p.battlefield),5);sim.invariant()
 def test_all_simultaneous_entrants_see_each_other(self):
  first=self.card('Goblin Instigator','first',oracleText='Whenever another creature you control enters, this creature deals 1 damage to each opponent.')
  second=self.card('Goblin Instigator','second',oracleText='Whenever another creature you control enters, this creature deals 1 damage to each opponent.')
  sim,source=self.fixture([first,second]);sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(len(sim.stack.items),2)
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  self.assertEqual(sim.players[1].life,38);sim.invariant()
 def test_short_empty_library_and_unknown_matching_creature(self):
  sim,source=self.fixture([])
  # Return the existing library to hand to retain physical card conservation.
  sim.players[0].hand+=sim.players[0].library;sim.players[0].library=[]
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertFalse(sim.players[0].failed_draw);self.assertFalse(sim.finished);sim.invariant()
  unsupported=self.card('Goblin Instigator','unknown',oracleText='Draw nine cards at random.')
  sim,source=self.fixture([unsupported]);before=list(sim.players[0].library)
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual(sim.result,'blocked');self.assertEqual(sim.players[0].library,before)
  self.assertTrue(any(q['card']==unsupported.name for q in sim.questions));sim.invariant()
 def test_attack_bonus_counts_at_resolution_and_expires(self):
  one=self.card('Goblin Instigator','one',oracleText='')
  two=self.card('Goblin Instigator','two',oracleText='')
  sim,source=self.fixture([one,two])
  while sim.stack.items:sim.pass_priority(sim.stack.priority)
  item=next(p for p in sim.players[0].battlefield if p.card.id==source.id);item.fresh=False
  game=sim.event_game('combat');game.attack(source.id,1,defer=True);sim.sync_events(game)
  sim.resolve_entry_triggers([e for e in game.events if e['kind']=='trigger'],source)
  self.assertEqual(sim.effective_card(item).power,4)
  sim.send_to_destination(sim.players[0],next(p for p in sim.players[0].battlefield if p.card.id=='two'))
  sim.pass_priority(0);sim.pass_priority(1)
  self.assertEqual((sim.effective_card(item).power,sim.effective_card(item).toughness),(5,5))
  sim.phase='cleanup';sim.step();self.assertEqual(sim.effective_card(item).power,4)
 def test_unfamiliar_program_rejects_extra_text(self):
  raw=dict(self.lookup['Muxus, Goblin Grandee'],name='Unknown, Leader')
  raw['oracleText']=raw['oracleText'].replace('Muxus','Unknown').replace('six','three').replace('Goblin','Elf').replace('5 or less','2 or less')
  card=s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'})
  self.assertEqual(card.kind,'creature')
  self.assertEqual(card.event_definition.triggers[0].effect.library_filter,(3,'Elf',2))
  raw['oracleText']+='\nDraw a card.'
  self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'x',{'Red'}).kind,'unsupported')
 def test_mana_values(self):
  for cost,value in [('',0),('{0}',0),('{X}{X}{R}',1),('{3}{R}{R}',5),('{W/U}{2/W}{B/P}{C}',5),('{W/U/P}',1),('{bad}',None)]:
   self.assertEqual(mana_value(cost),value)
