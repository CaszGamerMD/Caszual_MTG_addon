"""Compiled semantics are usable for strategies, but only if whole-card rules compile."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from compiled_rules_knowledge import compile_knowledge,analyze_known_cards

HERE=Path(__file__).resolve().parents[1]
ELVES=json.loads((HERE/'decks/14435337-lupitas-elves.json').read_text())


class CompiledKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def test_marwyn_exposes_reusable_trigger_counter_and_mana_semantics(self):
        card=ELVES['commanders'][0]
        k=compile_knowledge(self.rules,card)
        self.assertTrue(k['supported'])
        self.assertIn('mana_engine',k['roles'])
        self.assertIn('counter_growth',k['roles'])
        trigger=next(x for x in k['rules'] if x['timing']=='trigger')
        self.assertEqual(trigger['event'],'enters')
        self.assertEqual(trigger['subject']['subtype'],'Elf')
        self.assertEqual(trigger['steps'][0]['operation'],'self_counter')
        mana=next(x for x in k['rules'] if x['timing']=='activated')
        self.assertEqual(mana['cost'],'{T}')
        self.assertEqual(mana['color'],'G')
        self.assertEqual(mana['amountBasis'],'current effective power')

    def test_unknown_combination_produces_compiled_sequence(self):
        raw=dict(ELVES['commanders'][0],
            name='Unseen green apprentice',
            oracleText='When this creature enters, create a 1/1 green Elf Warrior creature token, then draw a card.',
            manaCost='{2}{G}',power='2',toughness='2')
        k=compile_knowledge(self.rules,raw)
        self.assertTrue(k['supported'])
        effects=k['rules'][0]['steps']
        self.assertEqual([x['operation'] for x in effects],
                         ['create_tokens','draw_cards'])
        self.assertEqual(effects[0]['token']['subtypes'],['Elf','Warrior'])
        self.assertIn('token_supply',k['roles'])
        self.assertIn('card_engine',k['roles'])

    def test_unknown_remainder_never_masquerades_as_known_strategy(self):
        raw=dict(ELVES['commanders'][0])
        raw['oracleText']=raw['oracleText']+'\nWhenever a dragon blinks, transcend destiny.'
        k=compile_knowledge(self.rules,raw)
        self.assertFalse(k['supported'])
        self.assertEqual(k['roles'],[])
        self.assertEqual(k['rules'],[])
        self.assertTrue(k['diagnosticOnly'])

    def test_deck_evidence_contains_explicit_uncompiled_cards(self):
        limited=dict(sourceDeckId=42,name='Unknown',
                     commanders=ELVES['commanders'],
                     mainboard=[ELVES['mainboard'][0]])
        k=analyze_known_cards(self.rules,limited)
        self.assertEqual(k['deckId'],42)
        self.assertEqual(len(k['confirmedRules'])+len(k['uncompiledCards']),2)
        self.assertTrue(k['diagnosticOnly'])


if __name__=='__main__':
    unittest.main()
