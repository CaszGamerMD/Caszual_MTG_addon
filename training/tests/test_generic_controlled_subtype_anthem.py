"""Subtype-controlled P/T grants must be continuous and owner-scoped."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import Game, Permanent, parse_card
from oracle_abilities import static_effect
import simulator as s


def creature(name,tribe,text='',power=2,toughness=2):
    return dict(name=name,types=['Creature'],subTypes=[tribe],superTypes=[],
                manaCost='{2}{W}',colors=['White'],colorIdentity=['White'],
                oracleText=text,power=str(power),toughness=str(toughness))


class ControlledTribalAnthemTests(unittest.TestCase):
    def test_signed_anthem_compiles_for_unknown_creature_types(self):
        for tribe in ('Sliver','Elf','Ooze','Goblin'):
            for bonus in ('+0/+1','+2/+0','-1/-1'):
                with self.subTest(tribe=tribe,bonus=bonus):
                    effect=static_effect(f'{tribe} creatures you control get {bonus}.')
                    self.assertIsNotNone(effect)
                    self.assertEqual(effect.subject.relation,'controller')
                    self.assertEqual(effect.subject.subtype,tribe)
        self.assertIsNone(static_effect('Sliver creatures you control get +0/+1 and teleport.'))

    def test_controller_only_and_source_included(self):
        leader=parse_card(creature('Unknown Sliver Instructor','Sliver',
                                  'Sliver creatures you control get +0/+1.'))
        self.assertTrue(leader.supported,leader.reason)
        ally=parse_card(creature('Ally','Sliver'))
        enemy=parse_card(creature('Enemy','Sliver'))
        outsider=parse_card(creature('Outsider','Elf'))
        g=Game()
        leader_p=Permanent('leader',leader,0)
        ally_p=Permanent('ally',ally,0)
        enemy_p=Permanent('enemy',enemy,1)
        other_p=Permanent('other',outsider,0)
        g.battlefield={p.id:p for p in (leader_p,ally_p,enemy_p,other_p)}
        self.assertEqual(g.stats(leader_p),(2,3))
        self.assertEqual(g.stats(ally_p),(2,3))
        self.assertEqual(g.stats(enemy_p),(2,2))
        self.assertEqual(g.stats(other_p),(2,2))
        del g.battlefield['leader']
        self.assertEqual(g.stats(ally_p),(2,2))

    def test_full_card_rejects_unknown_remainder(self):
        raw=creature('Unknown Sliver Instructor','Sliver',
                     'Sliver creatures you control get +0/+1.')
        self.assertTrue(parse_card(raw).supported)
        self.assertFalse(parse_card(dict(raw,oracleText=raw['oracleText']+
                                          '\nCreate an infinite time loop.')).supported)

    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def test_diagnostic_import_accepts_new_grammar(self):
        raw=creature('Unknown Sliver Instructor','Sliver',
                     'Sliver creatures you control get +0/+1.')
        result=s.import_diagnostic_card(self.rules,raw,0,'sliver',{'White'})
        self.assertEqual(result.kind,'creature')
        self.assertEqual(result.event_definition.static_effects[0].subject.relation,
                         'controller')


if __name__=='__main__':
    unittest.main()
