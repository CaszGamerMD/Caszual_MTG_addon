"""New rule block: intrinsic protection is a parameterized color keyword.

The parser should understand any text/color/creature name combination. In
combat and targeting, the existing game kernel interprets protection.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card, Permanent, Game

def subject(color, name="Unknown Defender"):
    return dict(name=name, types=['Creature'],subTypes=['Shade'],
                superTypes=[],power='5',toughness='5',
                colors=['Black'],oracleText=f"Protection from {color}")


class GenericProtectionTests(unittest.TestCase):
    def test_intrinsic_protection_all_mtg_colors(self):
        for color in ['white','blue','black','red','green']:
            with self.subTest(color=color):
                raw=subject(color, 'Unknown '+color.title()+' Guardian')
                definition=parse_card(raw)
                self.assertTrue(definition.supported)
                self.assertIn('protection from '+color,definition.abilities)
        self.assertFalse(parse_card(subject('purple')).supported)

    def test_cannot_hide_unrecognized_extra_instruction(self):
        card=subject('white')
        card['oracleText']+='\nTeleport a creature to nowhere.'
        self.assertFalse(parse_card(card).supported)

    def test_keyword_is_preserved_with_independent_trigger(self):
        card=subject('white','Unknown Archivist')
        card['oracleText']=('Protection from white\n'
            'Whenever another creature you control enters, draw a card.')
        parsed=parse_card(card)
        self.assertTrue(parsed.supported)
        self.assertEqual(len(parsed.triggers),1)
        self.assertIn('protection from white',parsed.abilities)


if __name__=='__main__':
    unittest.main()
