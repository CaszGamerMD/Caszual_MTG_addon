"""Whole-text damage-history exile, with casting and resolution legality."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_exile_creature_life as base

class ReciprocateChecks(unittest.TestCase):
    setUpClass=classmethod(base.ExileCreatureLifeChecks.setUpClass.__func__)
    tearDownClass=classmethod(base.ExileCreatureLifeChecks.tearDownClass.__func__)
    fixture=base.ExileCreatureLifeChecks.fixture
    creature=base.ExileCreatureLifeChecks.creature
    drain=base.ExileCreatureLifeChecks.drain

    def test_full_oracle_unseen_name_and_unknown_remainder(self):
        raw=dict(self.lookup['Reciprocate'],name='Unseen retaliatory spell')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'White'})
        self.assertEqual((card.kind,card.removal),('removal_spell','exile_creature_damaged_you'))
        raw['oracleText']+='\nDraw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_damage_creates_legal_target_and_exile_resolves_later(self):
        sim,cards=self.fixture(['Reciprocate'])
        attacker=self.creature(sim,'attacker',seat=1)
        with self.assertRaisesRegex(ValueError,'legal permanent'):
            sim.cast_spell(0,cards['Reciprocate'],target=attacker.card.id)
        sim.record_player_damage(0,attacker.card.id,3)
        sim.cast_spell(0,cards['Reciprocate'],target=attacker.card.id)
        self.assertIn(attacker,sim.players[1].battlefield)
        self.drain(sim)
        self.assertIn(attacker.card,sim.players[1].exile)
        sim.invariant()

    def test_illegal_if_history_expires_or_source_leaves_or_gains_hexproof(self):
        for mode in ('new_turn','leave','hexproof'):
            sim,cards=self.fixture(['Reciprocate'])
            target=self.creature(sim,'attacker',seat=1)
            sim.record_player_damage(0,target.card.id,1)
            sim.cast_spell(0,cards['Reciprocate'],target=target.card.id)
            if mode=='new_turn':sim.damage_to_players=[set(),set()]
            elif mode=='leave':sim.send_to_destination(sim.players[1],target)
            else:target.temporary_abilities=frozenset({'hexproof'})
            self.drain(sim)
            self.assertNotIn(target.card,sim.players[1].exile)
            sim.invariant()

    def test_actual_group_combat_records_damage_for_defending_player(self):
        sim,cards=self.fixture(['Reciprocate'])
        attacker=self.creature(sim,'attacker',seat=1,power=3)
        attacker.fresh=False
        sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
        sim.declare_attackers([attacker.card.id]);sim.declare_blockers({})
        while sim.group_combat is not None:
            sim.group_damage_step();self.drain(sim)
        self.assertEqual(sim.players[0].life,37)
        self.assertIn(attacker.card.id,sim.damage_to_players[0])
        sim.stack.priority=0
        sim.cast_spell(0,cards['Reciprocate'],target=attacker.card.id)
        self.drain(sim)
        self.assertIn(attacker.card,sim.players[1].exile)
        sim.invariant()

    def test_zero_damage_or_damage_to_opponent_does_not_qualify(self):
        sim,cards=self.fixture(['Reciprocate'])
        target=self.creature(sim,'attacker',seat=1)
        sim.record_player_damage(0,target.card.id,0)
        sim.record_player_damage(1,target.card.id,3)
        self.assertFalse(sim.removal_targets(0,cards['Reciprocate']))
        sim.invariant()
