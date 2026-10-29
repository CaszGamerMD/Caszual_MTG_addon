"""Whole Oracle attack-triggers grant temporary keywords to controlled team."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helper

class AttackTeamKeywordsChecks(unittest.TestCase):
    setUpClass=classmethod(helper.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helper.EnchantmentChecks.tearDownClass.__func__)
    fixture=helper.EnchantmentChecks.fixture
    put=helper.EnchantmentChecks.put
    token=helper.EnchantmentChecks.token
    drain=helper.EnchantmentChecks.drain

    def test_ankle_shanker_and_unseen_keyword_sets_parse_strictly(self):
        raw=dict(self.lookup['Ankle Shanker'],name='Unseen attacking captain')
        parsed=s.import_diagnostic_card(self.rules,raw,0,'captain',set())
        self.assertEqual(parsed.kind,'creature')
        self.assertEqual(parsed.event_definition.attack_effects[0][0],'attack_team_keywords')
        self.assertEqual(set(parsed.event_definition.attack_effects[0][3]),{'first strike','deathtouch'})
        other=dict(raw,oracleText='Haste\nWhenever this creature attacks, creatures you control gain vigilance and lifelink until end of turn.')
        card=s.import_diagnostic_card(self.rules,other,0,'other',set())
        self.assertEqual(set(card.event_definition.attack_effects[0][3]),{'vigilance','lifelink'})
        other['oracleText']+='\nUnrecognized instruction.'
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad',set()).kind,'unsupported')

    def test_team_grant_resolves_before_blockers_and_disappears_at_cleanup(self):
        sim,cards=self.fixture(['Ankle Shanker'])
        shanker=self.put(sim,cards['Ankle Shanker'])
        ally=self.token(sim,'ally',power=2,toughness=2)
        foe=self.token(sim,'foe',seat=1,power=2,toughness=2)
        for p in sim.players[0].battlefield:p.fresh=False
        sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([shanker.card.id])
        self.assertEqual(len(sim.stack.items),1)
        self.assertNotIn('deathtouch',sim.effective_card(ally).traits)
        self.drain(sim)
        for card in (shanker,ally):
            self.assertIn('first strike',sim.effective_card(card).traits)
            self.assertIn('deathtouch',sim.effective_card(card).traits)
        self.assertNotIn('deathtouch',sim.effective_card(foe).traits)
        game=sim.event_game('combat');game.cleanup();sim.sync_events(game)
        self.assertNotIn('deathtouch',sim.effective_card(ally).traits)
        sim.invariant()

    def test_ability_stays_on_stack_when_source_leaves(self):
        sim,cards=self.fixture(['Ankle Shanker'])
        source=self.put(sim,cards['Ankle Shanker'])
        ally=self.token(sim,'ally')
        source.fresh=False;sim.phase='attack';sim.stack.priority=sim.active
        sim.declare_attackers([source.card.id])
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertIn('first strike',sim.effective_card(ally).traits)
        sim.invariant()
