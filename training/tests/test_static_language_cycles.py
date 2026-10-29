"""Whole-program static-language learning cycles; real cards plus unseen names."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures


class ArchetypeSuppressionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_real_and_unseen_oracle_and_unknown_clause_rejection(self):
        raw=dict(self.lookup['Archetype of Courage'],name='Unseen first strike law')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'White'})
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(len(parsed.event_definition.static_effects),2)
        self.assertEqual(parsed.event_definition.static_effects[1].suppress,'first strike')
        raw['oracleText']+='\nCreatures get mysterious powers.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            "Creatures your opponents control lose flying and can't have or gain first strike."))
        self.assertIsNotNone(compile_abilities(
            "Creatures your opponents control lose flying and can't have or gain flying."))

    def test_denial_beats_printed_temporary_and_anthem_grants(self):
        sim,cards=self.fixture(['Archetype of Courage'])
        own=self.token(sim,'ally')
        enemy=self.token(sim,'enemy',seat=1,keywords=('first strike',))
        source=self.put(sim,cards['Archetype of Courage'])
        game=sim.event_game('combat')
        self.assertTrue(game.has(game.battlefield['ally'],'first strike'))
        self.assertFalse(game.has(game.battlefield['enemy'],'first strike'))
        enemy.temporary_abilities=frozenset({'first strike'})
        game=sim.event_game('combat')
        self.assertFalse(game.has(game.battlefield['enemy'],'first strike'))
        self.assertNotIn('first strike',sim.effective_card(enemy).traits)
        sim.send_to_destination(sim.players[0],source)
        self.assertTrue(sim.event_game('combat').has(sim.event_game('combat').battlefield['enemy'],'first strike'))
        sim.invariant()

    def test_suppression_is_scoped_to_opponents_and_disappears_with_source(self):
        sim,cards=self.fixture(['Archetype of Courage'])
        source=self.put(sim,cards['Archetype of Courage'])
        ally=self.token(sim,'ally',keywords=('first strike',))
        foe=self.token(sim,'foe',seat=1,keywords=('first strike',))
        self.assertIn('first strike',sim.effective_card(ally).traits)
        self.assertNotIn('first strike',sim.effective_card(foe).traits)
        sim.send_to_destination(sim.players[0],source)
        self.assertIn('first strike',sim.effective_card(foe).traits)
        sim.invariant()
