"""Generic global tribal anthem semantics, tested on both controllers."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oracle_abilities import static_effect
from card_events import Game, Permanent, parse_card, Definition


def creature(name,tribe,power=2,toughness=2,text=''):
    return dict(name=name,types=['Creature'],subTypes=[tribe],superTypes=[],
                manaCost='{2}',colors=['Red'],oracleText=text,
                power=str(power),toughness=str(toughness))

class GlobalTribalAnthemTests(unittest.TestCase):
    def test_global_anthem_parsed_by_stat_shape_and_creature_subtype(self):
        for tribe in ('Minotaur','Elf','Goblin','Ooze'):
            effect=static_effect(f'{tribe} creatures get +1/+0.')
            self.assertIsNotNone(effect)
            self.assertEqual(effect.subject.relation,'any')
            self.assertEqual(effect.subject.subtype,tribe)
            self.assertEqual((effect.power,effect.toughness),(1,0))
        self.assertIsNone(static_effect('Ooze creatures get +1/+0, and teleport.'))

    def test_global_bonus_includes_opponent_and_not_different_creatures(self):
        lord=parse_card(creature('Anonymous Instructor','Minotaur',2,2,
                                 'Minotaur creatures get +1/+0.'))
        self.assertTrue(lord.supported)
        friend=parse_card(creature('Friend','Minotaur'))
        enemy=parse_card(creature('Enemy','Minotaur'))
        outsider=parse_card(creature('Outsider','Elf'))
        game=Game()
        src=Permanent('src',lord,0)
        p=Permanent('friendly',friend,0)
        e=Permanent('enemy',enemy,1)
        o=Permanent('other',outsider,1)
        game.battlefield={x.id:x for x in (src,p,e,o)}
        self.assertEqual(game.stats(p),(3,2))
        self.assertEqual(game.stats(e),(3,2))
        self.assertEqual(game.stats(o),(2,2))
        self.assertEqual(game.stats(src),(3,2))

    def test_new_subtype_not_named_card_hardcoding(self):
        raw=creature('Unknown Elf Teacher','Elf',1,1,
                     'Elf creatures get -1/-1.')
        d=parse_card(raw)
        self.assertTrue(d.supported)
        self.assertEqual((d.static_effects[0].power,d.static_effects[0].toughness),
                         (-1,-1))


if __name__=='__main__':
    unittest.main()
