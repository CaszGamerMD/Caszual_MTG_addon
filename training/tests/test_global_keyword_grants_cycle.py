"""Whole-Oracle global keyword grants, with both players and source removal."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class GlobalKeywordGrantCycle(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_real_renamed_parameter_and_unknown_clause(self):
        raw=self.lookup['Concordant Crossroads']
        parsed=s.import_diagnostic_card(self.rules,raw,0,'crossroads',{'Green'})
        self.assertEqual(parsed.kind,'enchantment')
        self.assertEqual(parsed.event_definition.static_effects[0].grant,'haste')
        variant=dict(raw,name='Unseen Global Blessing',oracleText='All creatures have vigilance.')
        new=s.import_diagnostic_card(self.rules,variant,0,'unseen',{'Green'})
        self.assertEqual(new.kind,'enchantment')
        self.assertEqual(new.event_definition.static_effects[0].grant,'vigilance')
        for text in ('All creatures have mystery.','All creatures have haste.\nWin the game.'):
            variant['oracleText']=text
            self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',{'Green'}).kind,'unsupported')

    def test_global_haste_affects_both_players_and_is_removed(self):
        sim,cards=self.fixture(['Concordant Crossroads'])
        own=self.token(sim,'own',seat=0)
        opponent=self.token(sim,'enemy',seat=1)
        game=sim.event_game('main')
        self.assertFalse(game.has(game.battlefield[own.card.id],'haste'))
        self.assertFalse(game.has(game.battlefield[opponent.card.id],'haste'))
        source=self.put(sim,cards['Concordant Crossroads'])
        game=sim.event_game('main')
        self.assertTrue(game.has(game.battlefield[own.card.id],'haste'))
        self.assertTrue(game.has(game.battlefield[opponent.card.id],'haste'))
        self.assertIn('haste',sim.effective_card(own).traits)
        sim.send_to_destination(sim.players[0],source)
        game=sim.event_game('main')
        self.assertFalse(game.has(game.battlefield[own.card.id],'haste'))
        self.assertFalse(game.has(game.battlefield[opponent.card.id],'haste'))
        sim.invariant()

if __name__=='__main__':unittest.main()
