"""Optional death-triggered any-target damage uses last-known source information."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class OptionalDeathDamageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_unseen_name_variable_damage_and_reject_unknown_text(self):
        raw=dict(self.lookup['Goblin Arsonist'],name='Unknown firestarter')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.triggers[0].effect.operation,'damage_any_target')
        raw['oracleText']=raw['oracleText'].replace('deal 1 damage','deal 3 damage')
        card=s.import_diagnostic_card(self.rules,raw,0,'three',{'Red'})
        self.assertEqual(card.event_definition.triggers[0].effect.amount,3)
        raw['oracleText']+='\nDraw an impossible extra card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')

    def test_death_queues_damage_and_source_need_not_survive(self):
        sim,cards=self.fixture(['Goblin Arsonist'])
        source=self.put(sim,cards['Goblin Arsonist'])
        before=sim.players[1].life
        sim.destroy_batch([(0,source)],source.card)
        self.assertNotIn(source,sim.players[0].battlefield)
        self.assertEqual(sim.players[1].life,before)
        self.assertEqual(sim.stack.items[-1].payload[0]['targetKind'],'player')
        self.drain(sim)
        self.assertEqual(sim.players[1].life,before-1)
        sim.invariant()

    def test_targeted_creature_damage_and_fizzle_after_target_leaves(self):
        sim,cards=self.fixture(['Goblin Arsonist'])
        target=self.token(sim,'enemy-target',seat=1,power=2,toughness=1)
        source=self.put(sim,cards['Goblin Arsonist'])
        with patch.object(sim,'choose_damage_target',return_value=('permanent',target.card.id)):
            sim.destroy_batch([(0,source)],source.card)
        self.drain(sim)
        self.assertNotIn(target,sim.players[1].battlefield)
        sim.invariant()

        sim,cards=self.fixture(['Goblin Arsonist'])
        target=self.token(sim,'enemy-target',seat=1,power=2,toughness=3)
        source=self.put(sim,cards['Goblin Arsonist'])
        with patch.object(sim,'choose_damage_target',return_value=('permanent',target.card.id)):
            sim.destroy_batch([(0,source)],source.card)
        sim.send_to_destination(sim.players[1],target,to_exile=True)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='damage_any_target_fizzle' for e in sim.events))
        sim.invariant()

    def test_optional_decline_and_protected_targets_are_not_legal(self):
        sim,cards=self.fixture(['Goblin Arsonist'])
        protected=self.token(sim,'protected',seat=1,colors=('White',),keywords=('protection from red',))
        source=self.put(sim,cards['Goblin Arsonist'])
        sim.destroy_batch([(0,source)],source.card)
        event=sim.stack.items[-1].payload[0]
        self.assertNotIn(('permanent',protected.card.id),sim.damage_trigger_targets(event))
        before=sim.players[1].life
        with patch.object(sim,'choose_optional_damage',return_value=False):
            self.drain(sim)
        self.assertEqual(sim.players[1].life,before)
        self.assertTrue(any(e['kind']=='damage_declined' for e in sim.events))
        sim.invariant()
