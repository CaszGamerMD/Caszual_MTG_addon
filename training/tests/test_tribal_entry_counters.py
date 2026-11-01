"""Whole-text triggered self-counters from another controlled subtype entry."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tribal_entry_counters import parse
import simulator as s


ORACLE=('Whenever another Warrior your team controls enters, '
        'put a +1/+1 counter on this creature.')


class TribalEntryCounterChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=ORACLE,name='Fictional champion'):
        raw=dict(name=name,layout='normal',types=['Creature'],subTypes=['Warrior'],
                 superTypes=[],colors=['Green'],manaCost='{2}{G}',power='2',
                 toughness='2',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'self-counter',{'Green'})

    @staticmethod
    def creature(uid,subtype,seat=0):
        return s.Card(uid,uid,'creature',mana_cost='{1}',power=2,toughness=2,traits='2;2;',
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),
                frozenset({subtype}),False,2,2,frozenset()))

    def fixture(self,source):
        friends=[self.creature('arrival-warrior','Warrior'),
                 self.creature('arrival-elf','Elf')]
        enemy=self.creature('opposing-warrior','Warrior',1)
        lands=[s.Card('warrior-land-'+str(i),'Mana','land',mask=63) for i in range(5)]
        sim=s.Simulator(self.rules,49,
            decks=(s.demo_deck(0)+[source]+friends+lands,s.demo_deck(1)+[enemy]),
            diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main';sim.active=0
        for seat,cards in ((0,[source]+friends+lands),(1,[enemy])):
            p=sim.players[seat]
            for card in cards:(p.hand if card in p.hand else p.library).remove(card)
        p=sim.players[0]
        p.battlefield.extend(s.Permanent(c) for c in [source]+lands)
        p.hand.extend(friends)
        sim.players[1].battlefield.append(s.Permanent(enemy))
        return sim,friends,enemy

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_champion_and_unfamiliar_name_compile_same_trigger(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Decorated Champion')
        real=s.import_diagnostic_card(self.rules,raw,0,'real-champion',{'Green'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual(real.event_definition.tribal_entry_counter,
                         self.source().event_definition.tribal_entry_counter)

    def test_source_counters_only_after_another_controlled_warrior_enters(self):
        source=self.source();sim,friends,enemy=self.fixture(source)
        opponent=sim.players[1]
        opponent.battlefield.remove(next(p for p in opponent.battlefield if p.card==enemy))
        opposing_events=sim.enter_creature(enemy,opponent)
        self.assertFalse(any(e.get('operation')=='self_counter' for e in opposing_events))
        sim.cast_spell(0,friends[0])
        self.drain(sim)
        champ=next(p for p in sim.players[0].battlefield if p.card==source)
        self.assertEqual(champ.counters,1)
        sim.cast_spell(0,friends[1]);self.drain(sim)
        self.assertEqual(champ.counters,1)
        sim.invariant()

    def test_changed_subtype_and_counter_count_then_source_leaves(self):
        oracle=('Whenever another Elf you control enters, '
                'put 3 +1/+1 counters on this creature.')
        source=self.source(oracle)
        intact,arrivals,_=self.fixture(source)
        intact.cast_spell(0,arrivals[1]);self.drain(intact)
        self.assertEqual(next(p for p in intact.players[0].battlefield
                              if p.card==source).counters,3)
        intact.invariant()
        sim,friends,_=self.fixture(source)
        sim.cast_spell(0,friends[1]);sim.pass_priority(sim.stack.priority)
        sim.pass_priority(sim.stack.priority)  # incoming Elf resolves, counter trigger queued
        source_state=next(p for p in sim.players[0].battlefield if p.card==source)
        self.assertEqual(source_state.counters,0)
        sim.players[0].battlefield.remove(source_state)
        sim.players[0].graveyard.append(source)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='trigger' for e in sim.events))
        sim.invariant()

    def test_fail_closed_extra_clauses_and_bad_controllers(self):
        for text in (ORACLE+' Draw a card.',
                     ORACLE.replace('another Warrior','a Warrior'),
                     ORACLE.replace('your team controls','opponents control'),
                     ORACLE.replace('a +1/+1 counter','a -1/-1 counter')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Creature']))
                self.assertEqual(self.source(text).kind,'unsupported')
        self.assertIsNone(parse(ORACLE,['Enchantment']))


if __name__=='__main__':unittest.main()
