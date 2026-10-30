"""Generic self-or-subtype triggers must watch opponents and the source itself."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import Game, Permanent, parse_card
import simulator as s


def creature(name,subtype,text=''):
    return dict(name=name,types=['Creature'],subTypes=[subtype],superTypes=[],
                manaCost='{3}{B}',colors=['Black'],colorIdentity=['Black'],
                oracleText=text,power='3',toughness='2')


def watcher(name='Unknown Grave Witness',subtype='Zombie'):
    return creature(name,subtype,
        f'Whenever {name} or another {subtype} dies, each opponent loses 1 life.')


class SelfOrTribeDeathTests(unittest.TestCase):
    def test_unseen_names_and_subtypes_compile(self):
        for subtype in ('Zombie','Elf','Goblin','Sliver'):
            d=parse_card(watcher('Unknown '+subtype+' Witness',subtype))
            self.assertTrue(d.supported,d.reason)
            self.assertEqual(len(d.triggers),1)
            self.assertEqual(d.triggers[0].event,'dies')
            self.assertEqual(d.triggers[0].subject.self_or_subtype,subtype)
            self.assertEqual(d.triggers[0].effect.operation,'lose_life')

    def test_source_and_opposing_subtype_dying_both_trigger(self):
        source=Permanent('source',parse_card(watcher()),0)
        friend=Permanent('friend',parse_card(creature('Friend','Zombie')),0)
        enemy=Permanent('enemy',parse_card(creature('Enemy','Zombie')),1)
        other=Permanent('other',parse_card(creature('Other','Elf')),1)
        g=Game()
        g.battlefield={p.id:p for p in (source,friend,enemy,other)}
        triggers=g.death_triggers(['source','enemy','other'])
        matches=[e for e in triggers if e.get('source')=='source']
        self.assertEqual(len(matches),2)
        self.assertEqual({e['dead'] for e in matches},{'source','enemy'})
        self.assertTrue(all(e['controller']==0 and e['amount']==1 and
                            e['operation']=='lose_life' for e in matches))
        self.assertEqual(len(g.death_triggers(['friend'])),1)

    def test_fail_closed_on_unknown_text(self):
        raw=watcher()
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+
                                          '\nDestroy the entire library of each player.')).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText'].replace(
            'another Zombie dies','another Zombie with haste dies'))).supported)

    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def test_diagnostic_import_preserves_full_trigger(self):
        raw=watcher('Unknown Grave Witness')
        card=s.import_diagnostic_card(self.rules,raw,0,'witness',{'Black'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.triggers[0].subject.self_or_subtype,'Zombie')


if __name__=='__main__':
    unittest.main()
