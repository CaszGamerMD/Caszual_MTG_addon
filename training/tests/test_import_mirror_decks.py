"""Deck importer tests: maybeboard isolation, quantities, card semantics."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_mirror_decks import convert_deck, convert_card, colors


def card(name,qty=1,categories=(),types=('Creature',),text=''):
    return dict(quantity=qty,categories=list(categories),
                card=dict(oracleCard=dict(name=name,types=list(types),
                     superTypes=[],subTypes=['Elf'] if 'Creature' in types else [],
                     colors=['Green'],colorIdentity=['Green'],
                     manaCost='{G}',text=text,power='1',toughness='1',
                     layout='normal',faces=[])))


class MirrorDeckImportTests(unittest.TestCase):
    def test_exclude_maybeboard_even_with_other_categories(self):
        rows=[card('Marwyn, the Nurturer',categories=('Commander',)),
              card('Forest',qty=35,categories=('Land',),types=('Land',)),
              card('Elf',qty=54,categories=('Ramp',)),
              card('Goblin Tokens',qty=10,categories=('Tokens',)),
              card('Optional',qty=24,categories=('Maybeboard','Ramp'))]
        deck,report=convert_deck(14435337,dict(id=14435337,name='Demo',cards=rows))
        self.assertEqual(report['activeCards'],100)
        self.assertEqual(report['excludedMaybeboardCopies'],24)
        self.assertEqual(report['lands'],35)
        self.assertIn('Goblin Tokens',[c['name'] for c in deck['mainboard']])
        self.assertEqual(sum(c['quantity'] for c in deck['mainboard']),99)
        self.assertNotIn('Optional',[c['name'] for c in deck['mainboard']])
        self.assertEqual(deck['commanders'][0]['name'],'Marwyn, the Nurturer')
        self.assertEqual(deck['mainboard'][0]['colorIdentity'],['Green'])

    def test_invalid_active_count_is_not_reported_as_game(self):
        rows=[card('Krenko',categories=('Commander',)),
              card('Goblin',qty=20)]
        with self.assertRaisesRegex(ValueError,'exactly 100'):
            convert_deck(14509839,dict(id=14509839,name='Short',cards=rows))

    def test_only_one_commander_and_no_sideboard_import(self):
        rows=[card('One',categories=('Commander',)),
              card('Two',categories=('Commander',)),
              card('Land',qty=98,types=('Land',))]
        with self.assertRaisesRegex(ValueError,'one commander'):
            convert_deck(14435337,dict(id=14435337,name='Double',cards=rows))

    def test_rules_text_and_faces_roundtrip(self):
        obj=card('Unknown')
        oracle=obj['card']['oracleCard']
        oracle['text']='Create a 1/1 green Elf creature token.'
        oracle['faces']=[dict(name='Face 1',manaCost='{R}',types=['Sorcery'],
                              superTypes=[],subTypes=[],text='Draw a card.',
                              colors=['Red'],power='',toughness=''),
                         dict(name='Face 2',manaCost='',types=['Land'],
                              superTypes=[],subTypes=[],text='{T}: Add {R}.',
                              colors=[],power='',toughness='')]
        oracle['layout']='modal_dfc'
        result=convert_card(obj)
        self.assertEqual(result['oracleText'],oracle['text'])
        self.assertEqual(result['faces'][1]['types'],['Land'])
        self.assertEqual(result['layout'],'modal_dfc')
        self.assertEqual(result['colors'],['Green'])
        self.assertEqual(colors(['R','G','U']),['Red','Green','Blue'])


if __name__=='__main__':
    unittest.main()
