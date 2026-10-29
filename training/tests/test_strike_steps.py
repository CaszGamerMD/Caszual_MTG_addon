import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_simulator

class StrikeChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rules=s.RulesBridge()
 @classmethod
 def tearDownClass(cls):cls.rules.close()
 def fixture(self,traits):
  helper=test_simulator.SimulatorChecks();helper.rules=self.rules
  sim,cards=helper.death_fixture(traits)
  helper.resolve_fixture_combat(sim,cards)
  return sim,cards
 def test_double_strike_trample_after_blocker_dies(self):
  sim,cards=self.fixture('3;3;double strike,trample')
  sim.step()
  self.assertEqual(sim.players[1].life,38)
  self.assertEqual(sim.phase,'regular_damage')
  self.assertEqual(sum(p.card.is_token for p in sim.players[1].battlefield),1)
  sim.step()
  self.assertEqual(sim.players[1].life,35)
  self.assertEqual(sim.phase,'second_main');sim.invariant()
 def test_blocked_double_striker_without_trample_stays_blocked(self):
  sim,cards=self.fixture('3;3;double strike')
  sim.step();sim.step()
  self.assertEqual(sim.players[1].life,40)
  self.assertEqual(len(sim.players[0].battlefield),1)
 def test_first_strike_lethal_player_damage_stops_death_triggers(self):
  sim,cards=self.fixture('3;3;first strike,trample')
  sim.players[1].life=1;sim.step()
  self.assertTrue(sim.finished);self.assertEqual(sim.winner,0)
  self.assertFalse(sim.players[1].battlefield)
  self.assertFalse(any(e['kind']=='stack_push' for e in sim.events))
 def test_instant_response_window_with_no_damage_triggers(self):
  sim,cards=self.fixture('3;5;double strike,trample')
  sim.players[1].battlefield[0].counters=3
  removed=sim.players[1].library.pop()
  instant=s.import_diagnostic_card(self.rules,dict(name='Unknown reprieve',types=['Instant'],manaCost='{0}',oracleText='You gain 2 life.'),1,removed.id,{'White'})
  sim.players[1].hand.append(instant)
  sim.step()
  self.assertIn(instant,sim.players[1].graveyard)
  self.assertEqual(sim.players[1].life,42)
  self.assertEqual(sim.phase,'regular_damage');sim.invariant()
 def test_deathtouch_trample_and_zero_power(self):
  damage=self.rules.query('combat','5;5;deathtouch,trample','6;6;',40,40)
  self.assertEqual(damage['damage'],4)
  self.assertTrue(damage['blockerDies'])
  zero=self.rules.query('combat','0;5;deathtouch,trample','6;6;',40,40)
  self.assertEqual(zero['damage'],0);self.assertFalse(zero['blockerDies'])
 def test_deathtouch_trample_double_strike_indestructible_marks(self):
  from dataclasses import replace
  sim,cards=self.fixture('5;5;double strike,deathtouch,trample')
  blocker=sim.players[1].battlefield[0]
  blocker.card=replace(blocker.card,event_definition=replace(blocker.card.event_definition,abilities=frozenset({'indestructible'})))
  sim.step()
  self.assertEqual(sim.players[1].life,36)
  self.assertEqual(blocker.marked_damage,1)
  sim.step()
  self.assertEqual(sim.players[1].life,31)
  self.assertIn(blocker,sim.players[1].battlefield)
  sim.invariant()
 def test_damage_marks_persist_until_cleanup(self):
  sim,cards=self.fixture('1;5;double strike')
  # Make the blocker survive both damage steps.
  sim.players[1].battlefield[0].counters=3
  sim.step();self.assertEqual(sim.players[1].battlefield[0].marked_damage,1)
  sim.step();self.assertEqual(sim.players[1].battlefield[0].marked_damage,2)
  sim.phase='cleanup';sim.step()
  self.assertTrue(all(p.marked_damage==0 for player in sim.players for p in player.battlefield))
