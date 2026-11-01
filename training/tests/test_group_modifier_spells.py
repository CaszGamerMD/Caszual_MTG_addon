"""Whole-Oracle, maximum-stat team modifier learning cycle."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from group_modifier_spells import parse
import simulator as s


ORACLE=('Until end of turn, creatures you control gain trample and get '
        '+X/+X, where X is the greatest power among creatures you control.')


class GroupModifierChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def spell(self,text=ORACLE,name='Unseen team spell',types=('Sorcery',)):
        raw=dict(name=name,layout='normal',types=list(types),subTypes=[],superTypes=[],
                 colors=['Green'],manaCost='{G}',oracleText=text)
        return s.import_diagnostic_card(self.rules,raw,0,'team-spell',{'Green'})

    @staticmethod
    def creature(uid,power,toughness,seat=0):
        return s.Card(uid,uid,'creature',power=power,toughness=toughness,
            traits=f'{power};{toughness};',
            event_definition=s.EventDefinition(uid,frozenset({'Creature'}),frozenset(),
                 False,power,toughness,frozenset()))

    def fixture(self,spell):
        mana=s.Card('team-mana','Forest','land',mask=16)
        allies=[self.creature('team-a',2,2),self.creature('team-b',4,4)]
        opponent=self.creature('team-enemy',8,8,1)
        sim=s.Simulator(self.rules,427,
            decks=(s.demo_deck(0)+[spell,mana]+allies,
                   s.demo_deck(1)+[opponent]),diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True;sim.phase='main'
        for seat,cards in ((0,[spell,mana]+allies),(1,[opponent])):
            player=sim.players[seat]
            for card in cards:(player.hand if card in player.hand else player.library).remove(card)
        p=sim.players[0]
        p.hand.append(spell)
        p.battlefield.extend(s.Permanent(c) for c in [mana]+allies)
        sim.players[1].battlefield.append(s.Permanent(opponent))
        return sim,allies,opponent

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def test_actual_deck_card_and_unfamiliar_name_share_semantics(self):
        deck=json.loads((Path(__file__).resolve().parents[1]/'decks/14435337-lupitas-elves.json').read_text())
        real=next(c for c in deck['mainboard'] if c['name']=='Overwhelming Stampede')
        imported=s.import_diagnostic_card(self.rules,real,0,'stampede',{'Green'})
        self.assertEqual(imported.kind,'group_modifier_spell')
        self.assertEqual(imported.group_modifier_program,self.spell().group_modifier_program)
        self.assertEqual(self.spell(name='Different unfamiliar name').kind,'group_modifier_spell')

    def test_dynamic_max_count_and_opponent_exclusion(self):
        spell=self.spell()
        sim,allies,enemy=self.fixture(spell)
        sim.cast_spell(0,spell)
        # A new maximum after casting but before resolution changes X.
        permanent=next(p for p in sim.players[0].battlefield if p.card==allies[0])
        permanent.temporary_power=5  # now 7 power, ahead of 4/4 ally
        self.drain(sim)
        game=sim.event_game('main')
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(14,9))
        self.assertEqual(game.stats(game.battlefield[allies[1].id]),(11,11))
        self.assertTrue(all(game.has(game.battlefield[c.id],'trample') for c in allies))
        self.assertEqual(game.stats(game.battlefield[enemy.id]),(8,8))
        self.assertEqual(next(x for x in sim.events if x['kind']=='group_modifier')['details']['amount'],7)
        sim.invariant()

    def test_changed_keyword_and_toughness_operand(self):
        text=ORACLE.replace('trample','vigilance').replace('greatest power','greatest toughness')
        spell=self.spell(text,types=('Instant',))
        self.assertEqual(spell.kind,'group_modifier_spell')
        sim,allies,_=self.fixture(spell)
        self.drain(sim)
        sim.cast_spell(0,spell)
        self.drain(sim)
        game=sim.event_game('main')
        self.assertTrue(all(game.has(game.battlefield[c.id],'vigilance') for c in allies))
        self.assertEqual(game.stats(game.battlefield[allies[0].id]),(6,6))

    def test_unknown_clauses_and_scopes_reject_whole_spell(self):
        for text in (ORACLE+' Draw a card.',ORACLE.replace('you control','all players control'),
                     ORACLE.replace('trample','entwine'),ORACLE.replace('get +X/+X','get +X/+2'),
                     ORACLE.replace('greatest power','number of Elves')):
            with self.subTest(text=text):
                self.assertIsNone(parse(text,['Sorcery']))
                self.assertEqual(self.spell(text).kind,'unsupported')
        self.assertEqual(self.spell(types=('Creature',)).kind,'unsupported')


if __name__=='__main__':unittest.main()
