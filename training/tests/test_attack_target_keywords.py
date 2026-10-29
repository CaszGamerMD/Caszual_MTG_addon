"""Attack triggers target controlled legendary/nonlegendary creatures on the stack."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from attack_abilities import compile as compile_attacks
import test_enchantment_abilities as fixtures

class AttackTargetKeywordChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def legend(self,sim,identifier,seat=0):
        item=self.token(sim,identifier,seat=seat)
        item.card=replace(item.card,event_definition=replace(item.card.event_definition,legendary=True))
        return item

    def test_real_card_unseen_name_and_unknown_text_rejection(self):
        raw=dict(self.lookup['Mirkwood Spider'],name='Unseen legendary watcher')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Green'})
        self.assertEqual(card.kind,'creature')
        self.assertEqual(card.event_definition.attack_effects[0][0],'attack_target_keywords')
        raw['oracleText']+='\nWhen a mystery happens, do something unknown.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Green'}).kind,'unsupported')
        for kind in ('legendary','nonlegendary'):
            self.assertIsNotNone(compile_attacks(
                'Whenever this creature attacks, target '+kind+' creature you control gains flying and trample until end of turn.'))
        self.assertIsNone(compile_attacks(
            'Whenever this creature attacks, target legendary creature you control gains a mystery until end of turn.'))

    def test_target_legal_at_trigger_and_resolution_and_source_can_leave(self):
        sim,cards=self.fixture(['Mirkwood Spider'])
        target=self.legend(sim,'friendly-legend')
        self.legend(sim,'enemy-legend',seat=1)
        plain=self.token(sim,'plain')
        source=self.put(sim,cards['Mirkwood Spider'])
        self.ready(sim)
        sim.declare_attackers([source.card.id])
        self.assertTrue(sim.stack.items)
        self.assertEqual(sim.stack.items[-1].payload[0]['target'],target.card.id)
        self.assertNotIn('deathtouch',sim.effective_card(target).traits)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertIn('deathtouch',sim.effective_card(target).traits)
        self.assertNotIn('deathtouch',sim.effective_card(plain).traits)
        sim.invariant()

    def test_target_becomes_illegal_and_no_legal_target(self):
        sim,cards=self.fixture(['Mirkwood Spider'])
        target=self.legend(sim,'legend')
        source=self.put(sim,cards['Mirkwood Spider'])
        self.ready(sim);sim.declare_attackers([source.card.id])
        target.temporary_abilities=frozenset({'shroud'})
        self.drain(sim)
        self.assertTrue(any(e['kind']=='target_keywords_fizzle' for e in sim.events))
        sim.invariant()
        sim,cards=self.fixture(['Mirkwood Spider'])
        self.token(sim,'ordinary')
        source=self.put(sim,cards['Mirkwood Spider'])
        self.ready(sim);sim.declare_attackers([source.card.id])
        self.assertFalse(any(frame.payload[0].get('operation')=='grant_target_keywords' for frame in sim.stack.items))
        sim.invariant()
