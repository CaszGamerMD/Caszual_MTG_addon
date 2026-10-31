"""Saved-deck planeswalkers must retain printed loyalty yet fail closed."""
import sys
import json
import unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from planeswalker_inventory import report

class SavedPlaneswalkerChecks(unittest.TestCase):
    def test_real_faeries_cards_have_starting_loyalty_and_uncompiled_effects(self):
        decks=[json.loads(p.read_text(encoding='utf-8')) for p in
               sorted((HERE/'decks').glob('*.json'))]
        result=report(decks)
        names={x['name']:x for x in result['entries']}
        self.assertIn('Kaito Shizuki',names)
        self.assertIn('Liliana, the Last Hope',names)
        for name in ('Kaito Shizuki','Liliana, the Last Hope'):
            with self.subTest(name=name):
                card=names[name]
                self.assertEqual(card['startingLoyalty'],'3')
                self.assertTrue(card['executionReady'])
                self.assertEqual(len(card['loyaltyAbilities']),3)
        self.assertFalse(result['learningEligible'])

if __name__=='__main__':unittest.main()
