"""Life-gain history, conditional end-step triggers, and unseen Oracle grammar."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures


class EndStepLifeGainChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    drain=fixtures.EnchantmentChecks.drain
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    damage=fixtures.EnchantmentChecks.damage

    def with_aerie(self):
        sim,cards=self.fixture(['Griffin Aerie'])
        permanent=self.put(sim,cards['Griffin Aerie'])
        self.assertEqual(permanent.card.event_definition.triggers[0].event,'end_step')
        return sim,permanent

    def step_to_end(self,sim):
        sim.phase='end_step'
        sim.stack.priority=sim.active
        sim.step()

    def griffins(self,sim):
        return [p for p in sim.players[0].battlefield if p.card.is_token
                and p.card.event_definition and 'Griffin' in p.card.event_definition.subtypes]

    def test_exact_threshold_and_pre_resolution_stack(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,2);sim.gain_life(0,1)
        self.assertEqual(sim.life_gained_turn,[3,0])
        self.step_to_end(sim)
        self.assertEqual(len(sim.stack.items),1)
        self.assertEqual(len(self.griffins(sim)),0)
        self.drain(sim)
        self.assertEqual(len(self.griffins(sim)),1)
        griffin=self.griffins(sim)[0]
        self.assertEqual((griffin.card.power,griffin.card.toughness),(2,2))
        self.assertIn('flying',griffin.card.event_definition.abilities)
        sim.invariant()

    def test_end_step_keeps_priority_window_until_trigger_resolves(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,3)
        self.step_to_end(sim)
        self.assertEqual(sim.phase,'end_step')
        self.assertEqual(len(sim.stack.items),1)
        with self.assertRaisesRegex(RuntimeError,'Pending stack objects'):
            sim.step()
        self.drain(sim)
        self.assertEqual(len(self.griffins(sim)),1)
        sim.step()
        self.assertEqual(sim.phase,'cleanup')
        self.assertEqual(len(self.griffins(sim)),1)
        sim.invariant()

    def test_net_life_loss_does_not_erase_previous_gain(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,3)
        sim.players[0].life-=10
        self.assertEqual(sim.players[0].life,33)
        self.step_to_end(sim);self.drain(sim)
        self.assertEqual(len(self.griffins(sim)),1)
        sim.invariant()

    def test_below_threshold_and_other_players_gain_do_not_count(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,2);sim.gain_life(1,15)
        self.step_to_end(sim)
        self.assertFalse(sim.stack.items)
        self.assertFalse(self.griffins(sim))
        sim.invariant()

    def test_trigger_survives_source_leaving_stack(self):
        sim,source=self.with_aerie()
        sim.gain_life(0,3);self.step_to_end(sim)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(len(self.griffins(sim)),1)
        sim.invariant()

    def test_trigger_checks_at_step_start_not_after_later_gains(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,2);self.step_to_end(sim)
        sim.gain_life(0,4)
        self.assertEqual(len(self.griffins(sim)),0)
        self.assertFalse(sim.stack.items)

    def test_lifelink_from_group_combat_counts_toward_end_step(self):
        sim,_=self.with_aerie()
        attacker=self.token(sim,'lifelink-attacker',power=3,toughness=3,keywords=('lifelink',))
        self.ready(sim);sim.declare_attackers([attacker.card.id])
        sim.declare_blockers({});self.damage(sim)
        self.assertEqual(sim.life_gained_turn[0],3)
        self.step_to_end(sim);self.drain(sim)
        self.assertEqual(len(self.griffins(sim)),1)
        sim.invariant()

    def test_new_turn_resets_history_for_both_players(self):
        sim,_=self.with_aerie()
        sim.gain_life(0,5);sim.gain_life(1,7)
        sim.phase='end'
        sim.step()
        self.assertEqual(sim.life_gained_turn,[0,0])
        self.assertEqual(sim.active,1)
        sim.invariant()

    def test_whole_text_compiles_without_card_name_but_rejects_extra_rules(self):
        raw=dict(self.lookup['Griffin Aerie'],name='Unseen end-step token-maker')
        card=s.import_diagnostic_card(self.rules,raw,0,'different',{'White'})
        self.assertNotEqual(card.kind,'unsupported')
        ability=card.event_definition.triggers[0]
        self.assertEqual(ability.life_gained_at_least,3)
        self.assertEqual(ability.effect.operation,'create_tokens')
        raw['oracleText']+='\nAt the beginning of your end step, invent a new spell.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        self.assertIsNone(compile_abilities(
            'At the beginning of your end step, if you gained 3 or more life this turn, create a mystery.'))

    def test_threshold_and_token_stats_are_not_card_specific(self):
        text=('At the beginning of your end step, if you gained 5 or more life this turn, '
              'create a 1/1 green Squirrel creature token.')
        program=compile_abilities(text)
        self.assertIsNotNone(program)
        self.assertEqual(program.triggers[0].life_gained_at_least,5)
        spec=program.triggers[0].effect.token
        self.assertEqual((spec.power,spec.toughness,spec.subtypes),(1,1,('Squirrel',)))
