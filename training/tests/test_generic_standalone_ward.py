"""Parameterized ward composes without discarding unrelated Oracle text."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oracle_abilities import compile_abilities


class StandaloneWardTests(unittest.TestCase):
    def test_ward_cost_is_preserved(self):
        for cost in ('{1}', '{3}', '{W}', '{2}{U}', '{B}{B}'):
            with self.subTest(cost=cost):
                program=compile_abilities('Ward '+cost+'\nFlying', 'Unseen Guardian')
                self.assertIsNotNone(program)
                self.assertEqual(len(program.static_effects),1)
                self.assertEqual(program.static_effects[0].ward_cost,cost)
                self.assertIn('flying',program.keywords)

    def test_unknown_or_malformed_cost_fails_closed(self):
        for oracle in ('Ward {X}', 'Ward {3} and draw a card.',
                       'Ward {3}\nSacrifice a creature: draw three cards.',
                       'Ward {3}{', 'Ward {3} or pay 2 life'):
            with self.subTest(oracle=oracle):
                self.assertIsNone(compile_abilities(oracle,'Unseen Guardian'))


if __name__=='__main__':
    unittest.main()
