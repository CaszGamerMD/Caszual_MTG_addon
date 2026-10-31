"""Real saved Kaito: full Oracle import, end-step phase out and phase back in."""
import json
import sys
import unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import simulator as s
from planeswalker_loyalty import compile_card
from planeswalker_runtime import activate,legal

K=next(card for card in json.loads((HERE/'decks'/'27521806-faeries.json').read_text())['mainboard']
       if card['name']=='Kaito Shizuki')

class KaitoPhasingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=s.RulesBridge()
    @classmethod
    def tearDownClass(cls):cls.rules.close()

    def fixture(self):
        card=s.import_diagnostic_card(self.rules,K,0,'actual-kaito',{'Blue','Black'})
        self.assertEqual(card.kind,'planeswalker')
        lands=[s.Card('kaito-land-'+str(i),'Mana','land',mask=63) for i in range(6)]
        sim=s.Simulator(self.rules,81,
            decks=(s.demo_deck(0)+[card]+lands,s.demo_deck(1)),
            diagnostic=True)
        self.assertFalse(sim.finished,sim.questions)
        sim.manual_priority=True
        sim.phase='main'
        player=sim.players[0]
        for x in [card]+lands:
            (player.hand if x in player.hand else player.library).remove(x)
        player.hand.append(card)
        player.battlefield.extend(s.Permanent(x) for x in lands)
        sim.cast_spell(0,card)
        self.drain(sim)
        permanent=next(x for x in player.battlefield if x.card.id==card.id)
        return sim,card,permanent

    @staticmethod
    def drain(sim):
        while sim.stack.items:sim.pass_priority(sim.stack.priority)

    def end_step(self,sim):
        sim.active=0
        sim.stack.active=0
        sim.stack.priority=0
        sim.phase='end_step'
        sim._end_step_triggers_queued=False
        sim._step()

    def test_real_kaito_oracle_is_fully_compiled(self):
        program=compile_card(K)
        self.assertIsNotNone(program)
        self.assertEqual(program.starting_loyalty,3)
        self.assertTrue(program.phase_on_entry_end_step)
        self.assertEqual([x.effect_kind for x in program.abilities],[
            'draw_conditional_discard','unblockable_tokens','emblem'])
        custom=dict(K,name='Unfamiliar Walker',oracleText=
                    K['oracleText'].replace('Kaito entered this turn',
                                            'Unfamiliar Walker entered this turn'))
        self.assertIsNotNone(compile_card(custom))
        for wrong in (dict(K,name='Another Name'),
                      dict(K,oracleText=K['oracleText'].replace('he phases out',
                                                               'he is exiled')),
                      dict(K,oracleText=K['oracleText'].replace('your end step',
                                                               'each end step'))):
            with self.subTest(wrong=wrong):
                self.assertIsNone(compile_card(wrong))

    def test_phase_out_uses_stack_not_zone_change(self):
        sim,card,item=self.fixture()
        self.end_step(sim)
        self.assertFalse(item.phased_out)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(sim.stack.items[0].payload[0]['operation'],
                         'phase_on_entry_end_step')
        entry_count=len(sim.entry_history)
        self.drain(sim)
        self.assertTrue(item.phased_out)
        self.assertIn(item,sim.players[0].battlefield)
        self.assertNotIn(card,sim.players[0].graveyard)
        self.assertNotIn(card.id,sim.event_game('main').battlefield)
        self.assertEqual(item.loyalty,3)
        self.assertEqual(len(sim.entry_history),entry_count)
        self.assertFalse(legal(sim,0))
        sim.invariant()

    def test_phase_in_on_owner_next_untap_without_etb(self):
        sim,card,item=self.fixture()
        self.end_step(sim);self.drain(sim)
        before=len(sim.entry_history)
        sim.phase='end'
        sim._step()
        self.assertEqual(sim.active,1)
        self.assertTrue(item.phased_out)
        sim.phase='end'
        sim._step()
        self.assertEqual(sim.active,0)
        self.assertFalse(item.phased_out)
        self.assertIn(card.id,sim.event_game('main').battlefield)
        self.assertEqual(item.loyalty,3)
        self.assertEqual(len(sim.entry_history),before)
        sim.invariant()

    def test_countered_end_step_trigger_does_not_phase_out(self):
        sim,card,item=self.fixture()
        self.end_step(sim)
        frame=sim.stack.items[-1]
        self.assertIsNotNone(sim.counter_stack_item(frame))
        self.assertFalse(item.phased_out)
        self.assertIn(card.id,sim.event_game('main').battlefield)
        sim.invariant()

    def test_no_phase_trigger_if_not_entered_this_turn(self):
        sim,card,item=self.fixture()
        sim.turn=3
        self.end_step(sim)
        self.assertEqual(len(sim.stack.items),0)
        self.assertFalse(item.phased_out)
        sim.invariant()

    def test_resolving_after_source_leaves_does_not_phase(self):
        sim,card,item=self.fixture()
        self.end_step(sim)
        sim.players[0].battlefield.remove(item)
        sim.players[0].graveyard.append(card)
        self.drain(sim)
        self.assertTrue(any(e['kind']=='phase_out_no_source' for e in sim.events))
        self.assertNotIn(card.id,sim.event_game('main').battlefield)
        sim.invariant()

if __name__=='__main__':unittest.main()
