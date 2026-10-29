"""Cross-product checks for unseen combinations, independent of card names."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oracle_abilities import compile_abilities, cast_matches

class UnseenLanguageMatrixChecks(unittest.TestCase):
    def test_cast_filter_effect_cross_product(self):
        filters=['','artifact','creature','enchantment','instant','sorcery','planeswalker','noncreature']
        effects=[('draw a card.',['draw_cards']),('you gain 3 life.',['gain_life']),
                 ('you gain 2 life and draw two cards.',['gain_life','draw_cards']),
                 ('draw a card and you gain 4 life.',['draw_cards','gain_life'])]
        for noun in filters:
            for effect,operations in effects:
                with self.subTest(noun=noun,effect=effect):
                    text=f"Whenever you cast a {noun+' ' if noun else ''}spell, {effect}"
                    program=compile_abilities(text,'Unseen observer')
                    self.assertIsNotNone(program)
                    trigger=program.triggers[0]
                    parsed=trigger.effect
                    self.assertEqual([e.operation for e in parsed.steps] if parsed.steps else [parsed.operation],operations)
                    for types in [('Artifact',),('Creature',),('Enchantment',),('Instant',),('Sorcery',),('Planeswalker',),('Enchantment','Creature')]:
                        spell=SimpleNamespace(printed_types=types)
                        source=SimpleNamespace(controller=0)
                        expected=(not noun or ('Creature' not in types if noun=='noncreature' else noun.title() in types))
                        self.assertEqual(cast_matches(trigger,source,spell,0),expected)
                        self.assertFalse(cast_matches(trigger,source,spell,1))
                    self.assertIsNone(compile_abilities(text+'\nDo something unknown.','Unseen observer'))
                    self.assertIsNone(compile_abilities(text[:-1]+' and do something unknown.','Unseen observer'))
