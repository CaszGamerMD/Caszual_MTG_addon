"""Resolution-bound ETB team buffs with whole Oracle grammar."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entry_group_modifiers import parse
import simulator as s


ORACLE=('Haste\nWhen this creature enters, creatures you control gain trample '
        'and get +X/+X until end of turn, where X is the number of creatures '
        'you control.')


class EntryGroupModifierChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def card(self,text=ORACLE,name='Unseen arrival',subtype='Beast',types=('Creature',)):
        raw=dict(name=name,layout='normal',types=list(types),subTypes=[subtype],
                 superTypes=[],manaCost='{2}{G}',colors=['Green'],power='3',
                 toughness='3',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'team-arrival',{'Green'})

    @staticmethod
    def creature(uid,subtype,seat=0):
        return s.Card(uid,uid,'creature',power=2,toughness=3,traits='2;3;',
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),
                 frozenset({subtype}),False,2,3,frozenset()))

    def fixture(self,source):
        allies=[self.creature('arrival-ally','Elf'),self.creature('arrival-helper','Elf')]
        enemy=self.creature('arrival-enemy','Goblin',1)
        lands=[s.Card('arrival-land-'+str(i),'Mana','land',mask=63)
               for i in range(8)]
        sim=s.Simulator(self.rules,94,
            decks=(s.demo_deck(0)+[source]+allies+lands,
                   s.demo_deck(1)+[enemy]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        for seat,group in ((0,[source]+allies+lands),(1,[enemy])):
            p=sim.players[seat]
            for card in group:(p.hand if card in p.hand else p.library).remove(card)
        player=sim.players[0]
        player.hand.append(source)
        player.battlefield.extend(s.Permanent(x) for x in allies+lands)
        sim.players[1].battlefield.append(s.Permanent(enemy))
        return sim,allies,enemy

    @staticmethod
    def pass_pair(sim):
        sim.pass_priority(sim.stack.priority)
        sim.pass_priority(sim.stack.priority)

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_craterhoof_and_unfamiliar_card_use_same_program(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        real=next(c for c in deck['mainboard'] if c['name']=='Craterhoof Behemoth')
        actual=s.import_diagnostic_card(self.rules,real,0,'hoof',{'Green'})
        self.assertEqual(actual.kind,'creature')
        self.assertEqual(actual.event_definition.entry_group_modifier,
                         self.card().event_definition.entry_group_modifier)
        self.assertEqual(self.card(name='Completely unknown champion').kind,'creature')

    def test_trigger_uses_live_team_including_its_source_and_waits_on_stack(self):
        source=self.card()
        sim,allies,enemy=self.fixture(source)
        sim.cast_spell(0,source)
        self.pass_pair(sim)  # source enters; its triggered ability remains queued
        self.assertTrue(any(f.payload[0].get('operation')=='entry_group_modifier'
                            for f in sim.stack.items))
        game=sim.event_game('main')
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(2,3))
        self.assertTrue(game.has(game.battlefield[source.id],'haste'))
        self.drain(sim)
        game=sim.event_game('main')
        for card in [source]+allies:
            self.assertTrue(game.has(game.battlefield[card.id],'trample'))
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(5,6))
        self.assertEqual(game.stats(game.battlefield[enemy.id]),(2,3))
        self.assertEqual(next(e for e in sim.events if e['kind']=='entry_group_modifier')['details']['amount'],3)
        sim.phase='cleanup';sim.step()
        after=sim.event_game('main')
        self.assertEqual(after.stats(after.battlefield[allies[0].id]),(2,3))
        self.assertFalse(after.has(after.battlefield[allies[0].id],'trample'))
        sim.invariant()

    def test_source_departure_and_opponent_count_with_new_subtype(self):
        oracle=ORACLE.replace('Haste','Vigilance').replace('trample','flying').replace(
            'number of creatures you control','number of Goblins on the battlefield')
        source=self.card(oracle,name='Unseen mob leader',subtype='Goblin')
        self.assertEqual(source.kind,'creature')
        sim,allies,enemy=self.fixture(source)
        sim.cast_spell(0,source);self.pass_pair(sim)
        entered=next(p for p in sim.players[0].battlefield if p.card==source)
        sim.players[0].battlefield.remove(entered);sim.players[0].graveyard.append(entered.card)
        self.drain(sim)
        game=sim.event_game('main')
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(3,4))
        self.assertTrue(game.has(game.battlefield[allies[0].id],'flying'))
        self.assertEqual(game.stats(game.battlefield[enemy.id]),(2,3))
        sim.invariant()

    def test_rejects_unmatched_intrinsic_keywords_or_extra_sentences(self):
        for text in (ORACLE+'\nDraw a card.',
                     ORACLE.replace('Haste','Storm'),
                     ORACLE.replace('When this creature enters','Whenever an Elf enters'),
                     ORACLE.replace('+X/+X','+X/+2')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Creature']))
                self.assertEqual(self.card(text).kind,'unsupported')
        self.assertEqual(self.card(types=('Sorcery',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
