"""Unseen combat-damage trigger language and optional subtype put-from-hand."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class PutHandOnDamageChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def start_attack(self,sim,card):
        for perm in sim.players[0].battlefield:perm.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([card.card.id])
        sim.declare_blockers({})

    def test_real_lackey_and_instigator_and_unfamiliar_name_parse_strictly(self):
        for name,filter_kind in (('Goblin Lackey','permanent'),('Warren Instigator','creature')):
            original=self.lookup[name]
            unknown=dict(original,name='Unknown damage trigger')
            card=s.import_diagnostic_card(self.rules,unknown,0,'test',{'Red'})
            self.assertEqual(card.kind,'creature')
            triggers=[t for t in card.event_definition.triggers if t.event=='deals_player_damage']
            self.assertEqual(len(triggers),1)
            self.assertEqual(triggers[0].effect.operation,'optional_put_hand_permanent')
            self.assertEqual(triggers[0].effect.library_filter,('subtype','Goblin',filter_kind))
            unknown['oracleText']+='\nGain infinite life.'
            self.assertEqual(s.import_diagnostic_card(self.rules,unknown,0,'reject',set()).kind,'unsupported')
        original=self.lookup['Goblin Lackey']
        different=dict(original,name='Unknown elf recruiter',
            oracleText='Whenever this creature deals damage to a player, you may put an Elf permanent card from your hand onto the battlefield.')
        self.assertEqual(s.import_diagnostic_card(self.rules,different,0,'elf',set()).kind,'creature')

    def test_unblocked_lackey_puts_goblin_into_play_then_triggers_its_entry(self):
        sim,cards=self.fixture(['Goblin Lackey','Goblin Matron'])
        attacker=self.put(sim,cards['Goblin Lackey'])
        matron=cards['Goblin Matron']
        self.start_attack(sim,attacker)
        self.assertIn(matron,sim.players[0].hand)
        self.assertEqual(len([f for f in sim.stack.items if f.payload[0].get('operation')=='optional_put_hand_permanent']),1)
        self.drain(sim)
        self.assertNotIn(matron,sim.players[0].hand)
        self.assertTrue(any(p.card.id==matron.id for p in sim.players[0].battlefield))
        self.assertTrue(any(e['kind']=='put_from_hand' and e['details'].get('card')==matron.name for e in sim.events))
        # Enter-the-battlefield ability is queued on stack, not silently skipped.
        self.assertTrue(any(e['kind']=='search_reveal' or e['kind']=='search_declined' for e in sim.events))
        sim.invariant()

    def test_double_strike_creates_two_separate_hand_put_triggers(self):
        sim,cards=self.fixture(['Warren Instigator','Goblin Matron','Goblin Chieftain'])
        attacker=self.put(sim,cards['Warren Instigator'])
        self.start_attack(sim,attacker)
        self.assertEqual(sim.phase,'group_damage_start')
        sim.group_damage_step();self.drain(sim)
        self.assertTrue(any(p.card.id==cards['Goblin Matron'].id for p in sim.players[0].battlefield))
        self.assertEqual(sim.phase,'group_regular_damage')
        sim.group_damage_step();self.drain(sim)
        entered={p.card.id for p in sim.players[0].battlefield}
        self.assertIn(cards['Goblin Chieftain'].id,entered)
        self.assertEqual(len([e for e in sim.events if e['kind']=='put_from_hand']),2)
        sim.invariant()

    def test_declined_trigger_leaves_hand_and_combat_result_unchanged(self):
        sim,cards=self.fixture(['Goblin Lackey','Goblin Matron'])
        attacker=self.put(sim,cards['Goblin Lackey'])
        self.start_attack(sim,attacker)
        with patch.object(sim,'choose_optional_hand_permanent',return_value=None):
            self.drain(sim)
        self.assertIn(cards['Goblin Matron'],sim.players[0].hand)
        self.assertTrue(any(e['kind']=='hand_put_declined' for e in sim.events))
        sim.invariant()

    def test_blocked_attacker_does_not_put_a_card_from_hand(self):
        sim,cards=self.fixture(['Goblin Lackey','Goblin Matron'])
        attacker=self.put(sim,cards['Goblin Lackey'])
        defender=self.token(sim,'defender',seat=1,power=2,toughness=2)
        for p in sim.players[0].battlefield:p.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([attacker.card.id]);sim.declare_blockers({attacker.card.id:[defender.card.id]})
        while sim.group_combat is not None:
            sim.group_damage_step();self.drain(sim)
        self.assertIn(cards['Goblin Matron'],sim.players[0].hand)
        self.assertFalse(any(e['kind']=='put_from_hand' for e in sim.events))
        sim.invariant()

    def test_unrelated_creature_card_and_opponent_hand_not_eligible(self):
        sim,cards=self.fixture(['Goblin Lackey','Goblin Matron'])
        attacker=self.put(sim,cards['Goblin Lackey'])
        non_goblin=self.token(sim,'not-a-goblin',seat=1)
        other_hand=[c for c in sim.players[0].hand if c.kind=='creature' and 'Goblin' not in c.land_subtypes]
        self.assertFalse(any(c in sim.legal_hand_put_cards(0,'Goblin','creature') for c in other_hand))
        self.assertFalse(any(c in sim.legal_hand_put_cards(0,'Goblin','permanent') for c in other_hand))
        sim.invariant()
