"""Attacking-flying watch triggers: universal removal and defending damage."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helper

class FlyingAttackWatchersChecks(unittest.TestCase):
    setUpClass=classmethod(helper.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helper.EnchantmentChecks.tearDownClass.__func__)
    fixture=helper.EnchantmentChecks.fixture
    put=helper.EnchantmentChecks.put
    token=helper.EnchantmentChecks.token
    drain=helper.EnchantmentChecks.drain

    def test_saved_cards_and_renamed_templates_are_strict(self):
        for name,operation in (('Gravity Well','attacker_loses_flying'),('Raking Canopy','attacker_damage')):
            raw=dict(self.lookup[name],name='Unknown watcher')
            parsed=s.import_diagnostic_card(self.rules,raw,0,'watcher',set())
            self.assertEqual(parsed.kind,'enchantment')
            self.assertEqual(parsed.event_definition.attack_watchers[0][1],operation)
            invalid=dict(raw,oracleText=raw['oracleText']+'\nExtra unknown effect.')
            self.assertEqual(s.import_diagnostic_card(self.rules,invalid,0,'bad',set()).kind,'unsupported')
        raw=dict(self.lookup['Raking Canopy'],name='Big canopy',oracleText=
                 'Whenever a creature with flying attacks you, this enchantment deals 7 damage to it.')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'bigger',set())
        self.assertEqual(parsed.event_definition.attack_watchers[0][2],7)

    def test_gravity_well_removes_flying_before_blockers(self):
        sim,cards=self.fixture(['Gravity Well'])
        source=self.put(sim,cards['Gravity Well'])
        attacker=self.token(sim,'flier',power=2,toughness=2,keywords=('flying',))
        blocker=self.token(sim,'ground',seat=1,power=1,toughness=3)
        attacker.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        self.assertFalse(sim.can_block(attacker,blocker))
        sim.declare_attackers([attacker.card.id])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertFalse(sim.event_game('combat').has(sim.event_game('combat').battlefield[attacker.card.id],'flying'))
        self.assertTrue(sim.can_block(attacker,blocker))
        sim.invariant()

    def test_raking_canopy_only_damages_fliers_attacking_its_controller(self):
        sim,cards=self.fixture(['Raking Canopy'])
        self.put(sim,cards['Raking Canopy'])
        sim.active=1;sim.stack.priority=1
        attacker=self.token(sim,'bird',seat=1,power=2,toughness=2,keywords=('flying',))
        attacker.fresh=False
        sim.phase='attack'
        sim.declare_attackers([attacker.card.id])
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='attacker_damage' and e['details'].get('amount')==4 for e in sim.events))
        self.assertFalse(any(p.card.id==attacker.card.id for p in sim.players[1].battlefield))
        sim.invariant()

    def test_ground_creatures_do_not_trigger_either_watcher(self):
        sim,cards=self.fixture(['Gravity Well','Raking Canopy'])
        self.put(sim,cards['Gravity Well'])
        self.put(sim,cards['Raking Canopy'])
        attacker=self.token(sim,'walker',power=2,toughness=2)
        attacker.fresh=False;sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([attacker.card.id])
        self.assertFalse(any(frame.payload[0].get('operation') in
            ('attacker_damage','attacker_loses_flying') for frame in sim.stack.items))
        sim.invariant()
