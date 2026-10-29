"""Multi-tribe grants have one reusable text grammar and combat semantics."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class MultiTribeGrantsChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_real_and_renamed_oracle_compiles_without_ignoring_remainder(self):
        raw=dict(self.lookup['Caterwauling Boggart'],name='Unfamiliar tribe helper')
        card=s.import_diagnostic_card(self.rules,raw,0,'test',{'Red'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual({e.subject.subtype for e in card.event_definition.static_effects},{'Goblin','Elemental'})
        self.assertEqual({e.grant for e in card.event_definition.static_effects},{'menace'})
        variant=dict(raw,oracleText='Elves you control and Faeries you control have flying and lifelink.')
        card=s.import_diagnostic_card(self.rules,variant,0,'other',set())
        self.assertEqual(card.kind,'creature')
        self.assertEqual(len(card.event_definition.static_effects),4)
        self.assertEqual({e.subject.subtype for e in card.event_definition.static_effects},{'Elf','Faerie'})
        variant['oracleText']+='\nCreate a surprise token.'
        self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',set()).kind,'unsupported')
        variant['oracleText']='Goblins you control and Elementals you control have moonwalk.'
        self.assertEqual(s.import_diagnostic_card(self.rules,variant,0,'bad',set()).kind,'unsupported')

    def test_grant_filters_controller_and_subtype_and_vanishes_with_source(self):
        sim,cards=self.fixture(['Caterwauling Boggart'])
        boggart=self.put(sim,cards['Caterwauling Boggart'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        elemental=self.token(sim,'elemental',subtypes=('Elemental',))
        both=self.token(sim,'both',subtypes=('Goblin','Elemental'))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        for item in (goblin,elemental,both):self.assertIn('menace',sim.effective_card(item).traits)
        for item in (elf,enemy):self.assertNotIn('menace',sim.effective_card(item).traits)
        sim.send_to_destination(sim.players[0],boggart)
        self.assertNotIn('menace',sim.effective_card(goblin).traits)
        sim.invariant()

    def test_menace_rechecks_block_restriction_when_source_leaves(self):
        sim,cards=self.fixture(['Caterwauling Boggart'])
        boggart=self.put(sim,cards['Caterwauling Boggart'])
        goblin=self.token(sim,'goblin-attacker',subtypes=('Goblin',),power=4,toughness=4)
        blocker=self.token(sim,'blocker',seat=1,power=1,toughness=1)
        for p in sim.players[0].battlefield:p.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([goblin.card.id])
        with self.assertRaises(ValueError):sim.declare_blockers({goblin.card.id:[blocker.card.id]})
        sim.send_to_destination(sim.players[0],boggart)
        sim.declare_blockers({goblin.card.id:[blocker.card.id]})
        self.assertEqual(sim.group_combat['blocks'][goblin.card.id],[blocker.card.id])
        sim.invariant()
