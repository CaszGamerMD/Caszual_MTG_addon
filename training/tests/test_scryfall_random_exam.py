"""Offline deterministic Scryfall importer/exam tests; never make network calls."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import scryfall_random_exam as e


def fixture(n=1, **options):
    d=dict(object='card',id=f'printed-{n}',oracle_id=f'oracle-{n}',
           name=f'New creature {n}',type_line='Legendary Creature — Elf Druid',
           mana_cost='{1}{G}',oracle_text='Whenever this creature enters, draw a card.',
           colors=['G'],color_identity=['G'],games=['paper','mtgo'],
           legalities=dict(commander='legal'),layout='normal',
           power='2',toughness='2',scryfall_uri=f'https://scryfall.com/card/tst/{n}')
    d.update(options)
    return d


class ScryfallRandomExamTests(unittest.TestCase):
    def test_legal_card_and_type_conversion(self):
        card=e.convert_scryfall(fixture())
        self.assertEqual(card['types'],['Creature'])
        self.assertEqual(card['superTypes'],['Legendary'])
        self.assertEqual(card['subTypes'],['Elf','Druid'])
        self.assertEqual(card['colors'],['Green'])
        self.assertEqual(card['colorIdentity'],['Green'])
        self.assertEqual(card['oracleText'],'Whenever this creature enters, draw a card.')
        self.assertEqual(card['manaCost'],'{1}{G}')

    def test_banned_or_digital_card_is_rejected_even_if_api_misbehaves(self):
        with self.assertRaisesRegex(ValueError,'not paper Commander legal'):
            e.convert_scryfall(fixture(legalities=dict(commander='banned')))
        with self.assertRaisesRegex(ValueError,'not paper Commander legal'):
            e.convert_scryfall(fixture(games=['arena']))
        with self.assertRaisesRegex(ValueError,'Malformed'):
            e.convert_scryfall(dict(object='error',details='bad'))

    def test_modal_faces_are_preserved_without_synthesizing_new_rules(self):
        card=fixture(layout='modal_dfc',type_line='Land',
           mana_cost='',oracle_text='',card_faces=[
               dict(name='Spell Side',type_line='Sorcery',mana_cost='{G}',
                    oracle_text='Draw a card.',colors=['G']),
               dict(name='Land Side',type_line='Land',mana_cost='',
                    oracle_text='{T}: Add {G}.',colors=[])])
        data=e.convert_scryfall(card)
        self.assertEqual(data['layout'],'modal_dfc')
        self.assertEqual(len(data['faces']),2)
        self.assertEqual(data['faces'][0]['text'],'Draw a card.')
        self.assertEqual(data['faces'][1]['types'],['Land'])
        self.assertEqual(data['oracleText'],'')

    def test_five_cards_unique_oracle_identity_and_no_faked_samples(self):
        feed=iter([fixture(1),fixture(1,id='another-print'),fixture(2),
                   fixture(3),fixture(4),fixture(5)])
        seen=e.sample(5,1,fetch=lambda:next(feed),sleep=lambda _:None)
        self.assertEqual(len(seen),5)
        self.assertEqual([x['id'] for x,_ in seen],
                         ['printed-1','printed-2','printed-3','printed-4','printed-5'])
        with self.assertRaises(ValueError):
            e.sample(0,1,fetch=lambda:fixture())
        with self.assertRaisesRegex(RuntimeError,'only 1/5'):
            e.sample(5,1,fetch=lambda:fixture(),sleep=lambda _:None)

    def test_unknown_rules_do_not_become_executable_from_heuristic_hit(self):
        source=fixture(9,oracle_text='Create two 1/1 green Elf creature tokens and transcend time.')
        raw=e.convert_scryfall(source)
        class Card:
            kind='unsupported'
            event_definition=None
            name='unknown'
        with patch.object(e.s,'import_diagnostic_card',return_value=Card()), \
             patch.object(e.s,'parse_event_card') as parse:
            parse.return_value.reason='unparsed second instruction'
            row=e.analyze(object(),source,raw,0)
        self.assertFalse(row['executableDiagnostic'])
        self.assertIn('token_supply',row['hypotheticalRoles'])
        self.assertEqual(row['confirmedRoles'],[])
        self.assertEqual(row['gap'],'unparsed second instruction')


if __name__=='__main__':
    unittest.main()
