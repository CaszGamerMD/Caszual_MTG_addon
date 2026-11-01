"""ETB multi-card subtype search, revelation and ordered top placement."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entry_library_search import parse
import simulator as s


ORACLE=('When this creature enters, search your library for any number '
        'of Goblin cards, reveal them, then shuffle and put those cards '
        'on top in any order.')


class EntryLibrarySearchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=ORACLE,name='Unseen recruiter'):
        raw=dict(name=name,layout='normal',types=['Creature'],subTypes=['Goblin'],
                 superTypes=[],colors=['Red'],manaCost='{1}{R}',power='1',
                 toughness='1',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'library-recruiter',{'Red'})

    @staticmethod
    def creature(uid,subtype):
        return s.Card(uid,uid,'creature',power=2,toughness=2,traits='2;2;',
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),
                 frozenset({subtype}),False,2,2,frozenset()))

    def fixture(self,source):
        goblins=[self.creature('goblin-a','Goblin'),self.creature('goblin-z','Goblin'),
                 self.creature('goblin-m','Goblin')]
        other=self.creature('non-goblin','Elf')
        mana=[s.Card('recruit-land-'+str(i),'Mana','land',mask=63) for i in range(3)]
        sim=s.Simulator(self.rules,17,
            decks=(s.demo_deck(0)+[source]+goblins+[other]+mana,
                   s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        p=sim.players[0]
        for c in [source]+goblins+[other]+mana:
            (p.hand if c in p.hand else p.library).remove(c)
        p.hand.extend([source,other])
        p.library.extend(goblins)
        p.battlefield.extend(s.Permanent(x) for x in mana)
        return sim,goblins,other

    @staticmethod
    def pass_pair(sim):
        sim.pass_priority(sim.stack.priority)
        sim.pass_priority(sim.stack.priority)

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_real_recruiter_and_renamed_creature_compile_identically(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14509839-mono-red-gobs.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Goblin Recruiter')
        real=s.import_diagnostic_card(self.rules,raw,0,'recruit',{'Red'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual(real.event_definition.entry_top_library_search,
                         self.source().event_definition.entry_top_library_search)
        self.assertEqual(self.source(name='Fictional scout').kind,'creature')

    def test_reveal_shuffle_then_top_order_only_on_trigger_resolution(self):
        source=self.source()
        sim,goblins,other=self.fixture(source)
        p=sim.players[0]
        sim.cast_spell(0,source)
        self.pass_pair(sim)
        self.assertTrue(any(frame.payload[0].get('operation')=='entry_top_library_search'
                            for frame in sim.stack.items))
        self.assertFalse(any(e['kind']=='entry_search_reveal' for e in sim.events))
        # A matching creature added to the library before resolution is also
        # selectable; the search does not bind library identity on casting.
        p.hand.remove(other);p.library.append(other)
        self.drain(sim)
        expected=sorted(goblins,key=lambda c:c.id)
        self.assertEqual(p.library[-len(expected):],expected)
        self.assertTrue(any(e['kind']=='entry_search_reveal' and
            e['details']['cards']==[c.name for c in expected] for e in sim.events))
        self.assertEqual([e['kind'] for e in sim.events if e['kind'] in
                         ('entry_search','entry_search_reveal','library_shuffle','entry_search_top')][-4:],
                         ['entry_search','entry_search_reveal','library_shuffle','entry_search_top'])
        sim.invariant()

    def test_trigger_survives_source_leaving_and_zero_matches_still_shuffles(self):
        source=self.source(ORACLE.replace('Goblin','Elf'))
        sim,_,other=self.fixture(source)
        sim.players[0].hand.remove(other)
        sim.players[0].graveyard.append(other)
        sim.cast_spell(0,source);self.pass_pair(sim)
        entered=next(p for p in sim.players[0].battlefield if p.card==source)
        sim.players[0].battlefield.remove(entered)
        sim.players[0].graveyard.append(entered.card)
        self.drain(sim)
        events=[e for e in sim.events if e['kind']=='entry_search']
        self.assertEqual(events[-1]['details']['count'],0)
        self.assertEqual(sum(e['kind']=='entry_search_reveal' for e in sim.events),0)
        self.assertTrue(any(e['kind']=='entry_search_top' for e in sim.events))
        sim.invariant()

    def test_invalid_scopes_pronouns_and_extra_clause_reject(self):
        for text in (ORACLE+' Draw a card.',
                     ORACLE.replace('any number of','exactly two'),
                     ORACLE.replace('on top in any order','into your hand'),
                     ORACLE.replace('your library','an opponent\'s library')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Creature']))
                self.assertEqual(self.source(text).kind,'unsupported')
        self.assertIsNone(parse(ORACLE,['Artifact']))


if __name__=='__main__':unittest.main()
