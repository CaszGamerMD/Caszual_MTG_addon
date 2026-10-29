"""Reusable beginning-of-combat enchanted-creature target boosts."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures


class BeginningCombatBoostChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_full_oracle_unseen_name_parameters_and_unknown_clause(self):
        raw=dict(self.lookup['Nyx Herald'],name='Unknown combat herald')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.triggers[0].event,'begin_combat')
        raw['oracleText']=raw['oracleText'].replace('+1/+1 and gains trample','+2/+0 and gains flying')
        modified=s.import_diagnostic_card(self.rules,raw,0,'modified',{'Green'})
        self.assertEqual(modified.event_definition.triggers[0].effect.amount,2)
        self.assertEqual(modified.event_definition.triggers[0].effect.boost_keyword,'flying')
        raw['oracleText']+='\nDraw an impossible mystery.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'At the beginning of combat on your turn, target enchanted creature or enchantment creature you control gets +1/+1 and gains a mystery until end of turn.'))

    def test_combat_phase_queues_and_resolves_on_stack(self):
        sim,cards=self.fixture(['Nyx Herald'])
        herald=self.put(sim,cards['Nyx Herald'])
        before=sim.effective_card(herald).power
        sim.phase='main'
        with patch.object(sim,'decide',return_value=s.Candidate('pass','pass',features=s.features(**{'pass':1}),label='Pass')):
            sim._step()
        self.assertEqual(sim.phase,'attack')
        self.assertEqual(sim.effective_card(herald).power,before)
        self.assertTrue(sim.stack.items)
        self.assertEqual(sim.stack.items[-1].payload[0]['target'],herald.card.id)
        self.drain(sim)
        self.assertEqual(sim.effective_card(herald).power,before+1)
        self.assertIn('trample',sim.effective_card(herald).traits)
        sim.invariant()

    def test_legal_enchanted_target_and_recheck_at_resolution(self):
        sim,cards=self.fixture(['Nyx Herald','Audacity'])
        host=self.token(sim,'large-host',power=6,toughness=6)
        aura=self.put(sim,cards['Audacity'],host.card.id)
        source=self.put(sim,cards['Nyx Herald'])
        sim.active=0
        game=sim.event_game('combat');game.turn_player=0
        sim.resolve_entry_triggers(game.begin_combat_triggers(),source.card)
        self.assertEqual(sim.stack.items[-1].payload[0]['target'],host.card.id)
        sim.send_to_destination(sim.players[0],aura)
        self.drain(sim)
        self.assertTrue(any(event['kind']=='combat_boost_fizzle' for event in sim.events))
        self.assertNotIn('trample',sim.effective_card(host).traits)
        sim.invariant()

    def test_no_legal_target_does_not_create_stack_object(self):
        sim,cards=self.fixture(['Nyx Herald'])
        source=self.put(sim,cards['Nyx Herald'])
        sim.send_to_destination(sim.players[0],source)
        game=sim.event_game('combat');game.turn_player=0
        sim.resolve_entry_triggers(game.begin_combat_triggers(),source.card)
        self.assertFalse(sim.stack.items)
        sim.invariant()
