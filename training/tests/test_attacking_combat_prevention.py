"""Prevent only combat damage dealt to controlled attacking creatures."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class AttackingCombatPreventionChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    damage=fixtures.EnchantmentChecks.damage
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_oracle_and_unknown_clause(self):
        raw=dict(self.lookup['Dolmen Gate'])
        for name in ('Dolmen Gate','Unseen Battle Shelter'):
            raw['name']=name
            parsed=s.import_diagnostic_card(self.rules,raw,0,'gate',set())
            self.assertEqual(parsed.kind,'artifact')
            self.assertTrue(parsed.event_definition.prevent_combat_damage_to_attackers)
        raw['oracleText']+='\nPrevent all damage to every player.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',set()).kind,'unsupported')
        self.assertIsNone(compile_abilities('Prevent all combat damage that would be dealt to blocking creatures you control.'))

    def test_attacker_survives_deathtouch_lifelink_blocker_and_blocker_still_takes_damage(self):
        sim,cards=self.fixture(['Dolmen Gate'])
        gate=self.put(sim,cards['Dolmen Gate'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        blocker=self.token(sim,'blocker',seat=1,power=4,toughness=4,keywords=('deathtouch','lifelink'))
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({attacker.card.id:[blocker.card.id]})
        self.damage(sim)
        self.assertIn(attacker,sim.players[0].battlefield)
        self.assertEqual(attacker.marked_damage,0)
        self.assertEqual(blocker.marked_damage,2)
        self.assertEqual(sim.players[1].life,40)
        self.assertEqual(sim.life_gained_turn[1],0)
        sim.invariant()

    def test_removing_source_restores_damage_and_opponent_blockers_are_not_protected(self):
        sim,cards=self.fixture(['Dolmen Gate'])
        gate=self.put(sim,cards['Dolmen Gate'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        blocker=self.token(sim,'blocker',seat=1,power=4,toughness=4,keywords=('deathtouch',))
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({attacker.card.id:[blocker.card.id]})
        sim.send_to_destination(sim.players[0],gate)
        self.damage(sim)
        self.assertNotIn(attacker,sim.players[0].battlefield)
        self.assertEqual(blocker.marked_damage,2)
        sim.invariant()

    def test_single_attacker_damage_path_also_prevents_deathtouch_and_lifelink(self):
        sim,cards=self.fixture(['Dolmen Gate'])
        self.put(sim,cards['Dolmen Gate'])
        attacker=self.token(sim,'attacker',power=2,toughness=2)
        blocker=self.token(sim,'blocker',seat=1,power=4,toughness=4,
                           keywords=('deathtouch','lifelink'))
        sim.active=0;sim.phase='regular_damage'
        sim.combat_context=dict(attacker=attacker.card.id,blocker=blocker.card.id,
                                blocked=True,early=set())
        sim.strike_damage_step(False)
        self.assertIn(attacker,sim.players[0].battlefield)
        self.assertEqual(attacker.marked_damage,0)
        self.assertEqual(blocker.marked_damage,2)
        self.assertEqual(sim.players[1].life,40)
        sim.invariant()

    def test_first_strike_blocker_is_prevented_before_regular_damage(self):
        sim,cards=self.fixture(['Dolmen Gate'])
        self.put(sim,cards['Dolmen Gate'])
        attacker=self.token(sim,'attacker',power=3,toughness=2)
        blocker=self.token(sim,'blocker',seat=1,power=4,toughness=5,keywords=('first strike','lifelink'))
        self.ready(sim);sim.declare_attackers([attacker.card.id]);sim.declare_blockers({attacker.card.id:[blocker.card.id]})
        sim.group_damage_step()
        self.assertIn(attacker,sim.players[0].battlefield)
        self.assertEqual(attacker.marked_damage,0)
        self.assertEqual(sim.players[1].life,40)
        sim.group_damage_step()
        self.assertEqual(blocker.marked_damage,3)
        sim.invariant()

if __name__=='__main__':unittest.main()
