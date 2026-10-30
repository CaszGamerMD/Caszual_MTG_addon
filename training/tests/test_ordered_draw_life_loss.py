"""A draw-then-life-loss death trigger resolves in order for its controller."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures
from oracle_abilities import compile_abilities

class OrderedDrawLossChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_renamed_and_parameterized_whole_oracle(self):
        raw=dict(self.lookup['Tegwyll, Duke of Splendor'])
        real=s.import_diagnostic_card(self.rules,raw,0,'real',{'Blue','Black'})
        self.assertEqual(real.kind,'creature')
        self.assertEqual([step.operation for step in real.event_definition.triggers[0].effect.steps],['draw_cards','lose_life'])
        self.assertEqual(real.event_definition.triggers[0].effect.steps[1].recipient,'self')
        raw['name']='Unseen faerie ruler'
        raw['oracleText']=raw['oracleText'].replace('draw a card and you lose 1 life','draw two cards and you lose 3 life')
        other=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Blue','Black'})
        self.assertEqual([(e.operation,e.amount) for e in other.event_definition.triggers[0].effect.steps],
                         [('draw_cards',2),('lose_life',3)])
        raw['oracleText']+='\nYou win without playing.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Blue','Black'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Whenever another Faerie you control dies, you draw a card and you lose 1 life.\nUnknown future.'))

    def test_death_trigger_waits_on_stack_and_hits_correct_controller(self):
        sim,cards=self.fixture(['Tegwyll, Duke of Splendor'])
        ruler=self.put(sim,cards['Tegwyll, Duke of Splendor'])
        ally=self.token(sim,'ally',subtypes=('Faerie',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Faerie',))
        old_hand=len(sim.players[0].hand);old_life=sim.players[0].life
        self.assertEqual(sim.effective_card(ally).power,3)
        sim.destroy_batch([(1,enemy)],ruler.card)
        self.assertFalse(sim.stack.items)
        sim.destroy_batch([(0,ally)],ruler.card)
        self.assertTrue(any(frame.payload[0]['operation']=='ordered_effects' for frame in sim.stack.items))
        self.assertEqual((len(sim.players[0].hand),sim.players[0].life),(old_hand,old_life))
        self.drain(sim)
        self.assertEqual((len(sim.players[0].hand),sim.players[0].life),(old_hand+1,old_life-1))
        self.assertEqual(sim.players[1].life,40)
        sim.invariant()

    def test_source_leaving_does_not_cancel_trigger(self):
        sim,cards=self.fixture(['Tegwyll, Duke of Splendor'])
        ruler=self.put(sim,cards['Tegwyll, Duke of Splendor'])
        ally=self.token(sim,'ally',subtypes=('Faerie',))
        sim.destroy_batch([(0,ally)],ruler.card)
        before=sim.players[0].life
        sim.send_to_destination(sim.players[0],ruler)
        self.drain(sim)
        self.assertEqual(sim.players[0].life,before-1)
        sim.invariant()
