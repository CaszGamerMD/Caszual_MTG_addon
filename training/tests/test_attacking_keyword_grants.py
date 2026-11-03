"""Continuous attacking-creature keyword grants are parsed and scoped correctly."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import Definition,Game,Permanent
from oracle_abilities import compile_abilities


class AttackingKeywordChecks(unittest.TestCase):
    def test_real_bow_wording_compiles_as_a_continuous_attacking_filter(self):
        program=compile_abilities(
            'Attacking creatures you control have deathtouch.')
        self.assertIsNotNone(program)
        self.assertEqual(len(program.static_effects),1)
        effect=program.static_effects[0]
        self.assertTrue(effect.subject.attacking)
        self.assertEqual(effect.subject.relation,'controller')
        self.assertTrue(effect.subject.creature)
        self.assertEqual(effect.grant,'deathtouch')

    def test_grant_exists_only_while_the_creature_is_attacking(self):
        program=compile_abilities(
            'Attacking creatures you control have deathtouch.')
        source=Definition('Unfamiliar green artifact',
            frozenset({'Artifact','Enchantment'}),frozenset(),True,0,0,
            frozenset(),static_effects=program.static_effects)
        creature=Definition('Unfamiliar Elf',frozenset({'Creature'}),
            frozenset({'Elf'}),False,2,2,frozenset())
        game=Game(phase='combat')
        game.battlefield['source']=Permanent('source',source,0)
        attacker=Permanent('elf',creature,0,fresh=False)
        game.battlefield['elf']=attacker
        self.assertFalse(game.has(attacker,'deathtouch'))
        game.attack('elf',1)
        self.assertTrue(game.has(attacker,'deathtouch'))
        game.cleanup()
        self.assertFalse(game.has(attacker,'deathtouch'))

    def test_multiple_keywords_are_composed_and_unknown_text_rejects(self):
        program=compile_abilities(
            'Attacking creatures you control have deathtouch and vigilance.')
        self.assertIsNotNone(program)
        self.assertEqual({effect.grant for effect in program.static_effects},
                         {'deathtouch','vigilance'})
        self.assertIsNone(compile_abilities(
            'Attacking creatures you control have deathtouch.\\n'
            'Attacking creatures you control become invincible.'))


if __name__=='__main__':
    unittest.main()
