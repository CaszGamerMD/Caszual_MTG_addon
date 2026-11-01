"""Strict ETB same-name/creature-card intervening-if tests."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unique_entry_draw import parse
import simulator as s


ORACLE=("Whenever a nontoken creature you control enters, if it doesn't have "
        'the same name as another creature you control or a creature card in '
        'your graveyard, draw a card.')


class UniqueEntryDrawChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def source(self,text=ORACLE,name='Unfamiliar garden',types=('Enchantment',)):
        raw=dict(name=name,layout='normal',types=list(types),subTypes=[],
                 superTypes=[],colors=['Green'],manaCost='{2}{G}',oracleText=text)
        if 'Creature' in types:raw.update(power='1',toughness='4')
        return s.import_diagnostic_card(self.rules,raw,0,'unique-draw',{'Green'})

    @staticmethod
    def creature(uid,name='Unseen visitor'):
        return s.Card(uid,name,'creature',mana_cost='{1}',power=2,toughness=2,
            traits='2;2;',event_definition=s.EventDefinition(name,
                frozenset({'Creature'}),frozenset({'Elf'}),False,2,2,frozenset()))

    def fixture(self,source):
        incoming=self.creature('unique-arrival')
        duplicate=self.creature('unique-duplicate')
        other=self.creature('unique-other','Another type')
        lands=[s.Card('unique-land-'+str(i),'Mana','land',mask=63) for i in range(4)]
        sim=s.Simulator(self.rules,76,
            decks=(s.demo_deck(0)+[source,incoming,duplicate,other]+lands,
                   s.demo_deck(1)),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main';sim.active=0
        p=sim.players[0]
        for card in [source,incoming,duplicate,other]+lands:
            (p.hand if card in p.hand else p.library).remove(card)
        p.battlefield.extend(s.Permanent(c) for c in [source]+lands)
        p.hand.append(incoming)
        p.library.extend([duplicate,other])
        return sim,incoming,duplicate,other

    @staticmethod
    def pass_pair(sim):
        sim.pass_priority(sim.stack.priority)
        sim.pass_priority(sim.stack.priority)

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_guardian_project_and_unfamiliar_source_compile_equally(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        raw=next(c for c in deck['mainboard'] if c['name']=='Guardian Project')
        real=s.import_diagnostic_card(self.rules,raw,0,'guardian',{'Green'})
        self.assertEqual(real.kind,'enchantment')
        self.assertEqual(real.event_definition.unique_entry_draw,
                         self.source(name='Renamed entry garden').event_definition.unique_entry_draw)

    def test_unique_name_draws_after_stack_and_source_can_leave(self):
        source=self.source();sim,incoming,_,_=self.fixture(source)
        p=sim.players[0];before=len(p.hand)
        sim.cast_spell(0,incoming);self.pass_pair(sim)
        self.assertEqual(len(p.hand),before-1)
        self.assertTrue(any(f.payload[0].get('operation')=='unique_creature_entry_draw'
                            for f in sim.stack.items))
        watcher=next(item for item in p.battlefield if item.card==source)
        p.battlefield.remove(watcher);p.graveyard.append(source)
        self.drain(sim)
        self.assertEqual(len(p.hand),before)
        self.assertTrue(any(e['kind']=='unique_entry_draw' for e in sim.events))
        sim.invariant()

    def test_duplicate_on_battlefield_or_graveyard_blocks_trigger(self):
        for zone in ('battlefield','graveyard'):
            with self.subTest(zone=zone):
                sim,incoming,duplicate,_=self.fixture(self.source())
                p=sim.players[0];p.library.remove(duplicate)
                if zone=='battlefield':p.battlefield.append(s.Permanent(duplicate))
                else:p.graveyard.append(duplicate)
                sim.cast_spell(0,incoming);self.pass_pair(sim)
                self.assertFalse(any(f.payload[0].get('operation')=='unique_creature_entry_draw'
                                     for f in sim.stack.items))
                sim.invariant()

    def test_duplicate_arriving_before_resolution_fails_intervening_if(self):
        sim,incoming,duplicate,_=self.fixture(self.source())
        p=sim.players[0]
        sim.cast_spell(0,incoming);self.pass_pair(sim)
        self.assertTrue(sim.stack.items)
        p.library.remove(duplicate);p.graveyard.append(duplicate)
        before=len(p.hand)
        self.drain(sim)
        self.assertEqual(len(p.hand),before)
        self.assertTrue(any(e['kind']=='unique_entry_gate_failed' for e in sim.events))
        sim.invariant()

    def test_parameterized_two_card_draw_and_token_exclusion(self):
        oracle=ORACLE.replace('draw a card.','draw 2 cards.')
        source=self.source(oracle,types=('Creature',))
        sim,incoming,_,_=self.fixture(source)
        p=sim.players[0]
        token=self.creature('unique-token','Unique token')
        token=s.replace(token,is_token=True)
        pending=sim.enter_creature(token,p)
        self.assertFalse(any(e.get('operation')=='unique_creature_entry_draw' for e in pending))
        before=len(p.hand)
        sim.cast_spell(0,incoming);self.pass_pair(sim);self.drain(sim)
        self.assertEqual(len(p.hand),before-1+2)
        sim.invariant()

    def test_unmatched_oracle_syntax_remains_unsupported(self):
        for text in (ORACLE+' Gain 2 life.',
                     ORACLE.replace('nontoken','token'),
                     ORACLE.replace('your graveyard','any graveyard'),
                     ORACLE.replace('another creature','a creature')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Enchantment']))
                self.assertEqual(self.source(text).kind,'unsupported')


if __name__=='__main__':unittest.main()
