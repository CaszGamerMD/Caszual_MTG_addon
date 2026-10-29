import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from question_batches import build_report, recognized_component

class QuestionBatchChecks(unittest.TestCase):
    def test_shared_numeric_language_and_overlap_do_not_claim_resolution(self):
        questions=[dict(id=str(i),card=name,oracleText=text,occurrences=[dict(deckId=1,quantity=1)],encounterGames=['g1','g1'])
                   for i,(name,text) in enumerate([
                       ('Unknown A','Enchantment spells you cast cost {1} less to cast.\nWhenever you cast an enchantment spell, draw a card.'),
                       ('Unknown B','Enchantment spells you cast cost {2} less to cast.'),
                       ('Unknown C','')])]
        report=build_report(questions,1)
        costs=next(r for r in report['families'] if r['family']=='cost changes')
        self.assertEqual(costs['affectedCards'],2)
        self.assertEqual(costs['cardGameEncounters'],2)
        self.assertEqual(costs['cardsWithOtherCandidateFamilies'],1)
        self.assertEqual(report['repeatedClauseTemplates'][0]['affectedCards'],2)
        self.assertEqual(report['unresolvedCards'],3)
        self.assertTrue(any(r['family']=='multiple faces or missing Oracle text' for r in report['families']))
        self.assertEqual(report,build_report(list(reversed(questions)),1)|{'cards':report['cards']})

    def test_known_components_are_not_confused_with_complete_card_support(self):
        for text in ('Flying','Equip {2}','Enchant creature','Enchanted creature gets +1/+1 and has first strike.'):
            self.assertTrue(recognized_component(text,'Unseen source'),text)
        self.assertFalse(recognized_component('Whenever you blink, do something unknown.','Unseen source'))
