"""Controlled-creature Aura attachment restriction: casting and state-based legality."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from attachments import parse
import test_enchantment_abilities as fixtures

class OwnCreatureAuraChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def make_aura(self):
        raw=dict(self.lookup['Lifelink'],name='Unknown blessing',
                 oracleText='Enchant creature you control\nEnchanted creature gets +2/+1 and has first strike.')
        return s.import_diagnostic_card(self.rules,raw,0,'own-aura',{'White'}),raw

    def test_unseen_name_and_strict_unknown_clause(self):
        card,raw=self.make_aura()
        self.assertEqual(card.kind,'aura')
        self.assertEqual(card.event_definition.attachment[5],'controller')
        self.assertEqual(parse('Enchant creature\nEnchanted creature gets +2/+1.',{'Enchantment'},{'Aura'})[0],'aura')
        self.assertIsNone(parse('Enchant creature an opponent controls\nEnchanted creature gets +2/+1.',{'Enchantment'},{'Aura'}))
        raw['oracleText']+='\nDraw an unknown bonus card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')

    def test_enemy_cannot_be_enchanted_and_own_host_gets_stats(self):
        sim,_=self.fixture(['Lifelink'])
        aura,_=self.make_aura()
        sim.players[0].hand.append(aura)
        own=self.token(sim,'own-host')
        enemy=self.token(sim,'enemy-host',seat=1)
        self.assertNotIn(enemy.card.id,{p.card.id for _,p in sim.creature_targets(0,aura)})
        with self.assertRaises(ValueError):sim.cast_spell(0,aura,target=enemy.card.id)
        self.assertIn(aura,sim.players[0].hand)
        sim.cast_spell(0,aura,target=own.card.id)
        self.drain(sim)
        self.assertEqual(sim.effective_card(own).power,4)
        self.assertIn('first strike',sim.effective_card(own).traits)
        sim.invariant()

    def test_control_change_detaches_restricted_aura(self):
        sim,_=self.fixture(['Lifelink'])
        aura,_=self.make_aura()
        host=self.token(sim,'host')
        sim.enter_creature(aura,sim.players[0],attached_to=host.card.id)
        sim.players[0].battlefield.remove(host)
        sim.players[1].battlefield.append(host)
        sim.state_based_actions()
        self.assertNotIn(aura.id,[p.card.id for p in sim.players[0].battlefield])
        self.assertIn(aura.id,[c.id for c in sim.players[0].graveyard])
        sim.invariant()
