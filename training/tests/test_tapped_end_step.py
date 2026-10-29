"""Unconditional end-step triggers with tapped-creature counting at resolution."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class TappedEndStepChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def end_step(self,sim):
        sim.phase='end_step'
        sim.stack.active=sim.active
        sim.stack.priority=sim.active
        sim.step()

    def test_actual_and_unknown_name_parse_whole_text_fail_closed(self):
        raw=dict(self.lookup['Throne of the God-Pharaoh'],name='Unknown throne')
        card=s.import_diagnostic_card(self.rules,raw,0,'throne',{'Black'})
        self.assertEqual(card.kind,'artifact')
        ability=card.event_definition.triggers[0]
        self.assertEqual((ability.event,ability.effect.operation),
                         ('end_step','opponent_loss_tapped_creatures'))
        raw['oracleText']+='\nCreate a random impossible artifact.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')

    def test_only_tapped_friendly_creatures_count_not_tapped_lands(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        self.put(sim,cards['Throne of the God-Pharaoh'])
        first=self.token(sim,'first');second=self.token(sim,'second')
        self.token(sim,'third')
        enemy=self.token(sim,'enemy',seat=1)
        first.tapped=second.tapped=enemy.tapped=True
        next(p for p in sim.players[0].battlefield if p.card.kind=='land').tapped=True
        self.end_step(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(sim.players[1].life,40)
        self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[40,38])
        sim.invariant()

    def test_tapped_status_is_read_on_resolution_not_at_trigger_time(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        self.put(sim,cards['Throne of the God-Pharaoh'])
        first=self.token(sim,'first');second=self.token(sim,'second')
        first.tapped=True
        self.end_step(sim)
        first.tapped=False;second.tapped=True
        self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_source_leaving_after_trigger_does_not_cancel_ability(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        source=self.put(sim,cards['Throne of the God-Pharaoh'])
        self.token(sim,'first').tapped=True
        self.end_step(sim)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_zero_tapped_creatures_causes_zero_life_loss(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        self.put(sim,cards['Throne of the God-Pharaoh'])
        self.end_step(sim);self.drain(sim)
        self.assertEqual([p.life for p in sim.players],[40,40])
        sim.invariant()

    def test_end_step_queues_only_once_before_cleanup(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        self.put(sim,cards['Throne of the God-Pharaoh'])
        self.token(sim,'one').tapped=True
        self.end_step(sim);self.drain(sim)
        self.assertEqual(sim.players[1].life,39)
        sim.step()
        self.assertEqual(sim.phase,'cleanup')
        self.assertEqual(sim.players[1].life,39)
        sim.invariant()

    def test_opponents_end_step_does_not_trigger_our_throne(self):
        sim,cards=self.fixture(['Throne of the God-Pharaoh'])
        self.put(sim,cards['Throne of the God-Pharaoh'])
        self.token(sim,'one').tapped=True
        sim.active=1
        self.end_step(sim)
        self.assertFalse(sim.stack.items)
        self.assertEqual(sim.players[0].life,40)
        sim.invariant()
