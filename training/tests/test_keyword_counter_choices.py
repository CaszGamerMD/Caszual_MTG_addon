"""Keyword counter entry choices: complete Oracle and gameplay behavior."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as f
class KeywordCounterChoiceChecks(unittest.TestCase):
    setUpClass=classmethod(f.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(f.EnchantmentChecks.tearDownClass.__func__)
    fixture=f.EnchantmentChecks.fixture
    put=f.EnchantmentChecks.put
    def test_unseen_and_unknown_remainder(self):
        raw=dict(self.lookup['Boot Nipper'],name='Unknown Counter Beast')
        c=s.import_diagnostic_card(self.rules,raw,0,'u',{'Black'})
        self.assertEqual(c.event_definition.entry_keyword_choices,('deathtouch','lifelink'))
        other=dict(raw,oracleText='This creature enters with your choice of a flying counter or a reach counter on it.')
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'v',set()).event_definition.entry_keyword_choices,('flying','reach'))
        for suffix in ('\nDraw two cards.','\nCreate an unknown token.'):
            self.assertEqual(s.import_diagnostic_card(self.rules,dict(raw,oracleText=raw['oracleText']+suffix),0,'bad',set()).kind,'unsupported')
    def test_choice_persists_and_is_not_plus_one_counter(self):
        sim,cards=self.fixture(['Boot Nipper'])
        source=self.put(sim,cards['Boot Nipper'])
        self.assertEqual(source.keyword_counters,frozenset({'deathtouch'}))
        self.assertEqual(source.counters,0)
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[source.card.id],'deathtouch'))
        sim.invariant()
    def test_alternate_and_illegal_choice(self):
        sim,cards=self.fixture(['Boot Nipper']);card=cards['Boot Nipper']
        with self.assertRaises(ValueError):
            sim.enter_creature(card,sim.players[0],keyword_counter='flying')
        sim.players[0].hand.remove(card)
        sim.enter_creature(card,sim.players[0],keyword_counter='lifelink')
        self.assertTrue(sim.event_game('main').has(sim.event_game('main').battlefield[card.id],'lifelink'))
        sim.invariant()
