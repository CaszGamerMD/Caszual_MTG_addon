"""Mentor targeting and temporary begin-combat attack obligations."""
import unittest
import test_enchantment_abilities as fixtures
import simulator as s

class MentorCombatChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    ready=fixtures.EnchantmentChecks.ready
    drain=fixtures.EnchantmentChecks.drain

    def test_unseen_name_full_program_and_unknown_clause_rejected(self):
        raw=dict(self.lookup['Legion Warboss'],name='Unseen mentor captain')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'mentor',{'Red'}).kind,'creature')
        raw['oracleText']+='\nGain an unknown advantage.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')

    def test_begin_combat_token_temporary_haste_and_required_attack(self):
        sim,cards=self.fixture(['Legion Warboss'])
        source=self.put(sim,cards['Legion Warboss'])
        sim.active=0
        game=sim.event_game('combat');game.turn_player=0
        sim.resolve_entry_triggers(game.begin_combat_triggers(),source.card)
        self.assertEqual(len(sim.stack.items),1)
        self.drain(sim)
        created=[p for p in sim.players[0].battlefield if p.card.is_token]
        self.assertEqual(len(created),1)
        goblin=created[0]
        game=sim.event_game('combat')
        self.assertTrue(game.has(game.battlefield[goblin.card.id],'haste'))
        self.assertTrue(game.must_attack(game.battlefield[goblin.card.id]))
        self.ready(sim)
        with self.assertRaises(ValueError):sim.declare_attackers([source.card.id])
        sim.declare_attackers([source.card.id,goblin.card.id])
        self.drain(sim)
        sim.invariant()

    def test_mentor_counter_uses_attackers_and_resolves_on_stack(self):
        sim,cards=self.fixture(['Legion Warboss'])
        source=self.put(sim,cards['Legion Warboss'])
        small=self.token(sim,'small',power=1,toughness=2)
        large=self.token(sim,'large',power=4,toughness=4)
        self.ready(sim)
        sim.declare_attackers([source.card.id,small.card.id,large.card.id])
        self.assertEqual(small.counters,0)
        self.assertTrue(any(frame.payload[0].get('operation')=='mentor_counter' for frame in sim.stack.items))
        self.drain(sim)
        self.assertEqual(small.counters,1)
        self.assertEqual(large.counters,0)
        sim.invariant()

    def test_mentor_fizzles_when_target_grows_too_large(self):
        sim,cards=self.fixture(['Legion Warboss'])
        source=self.put(sim,cards['Legion Warboss'])
        small=self.token(sim,'small',power=1,toughness=2)
        self.ready(sim)
        sim.declare_attackers([source.card.id,small.card.id])
        small.counters=3
        self.drain(sim)
        self.assertEqual(small.counters,3)
        self.assertTrue(any(e['kind']=='mentor_fizzle' for e in sim.events))
        sim.invariant()

    def test_mentor_uses_source_last_known_power_if_source_leaves(self):
        sim,cards=self.fixture(['Legion Warboss'])
        source=self.put(sim,cards['Legion Warboss'])
        small=self.token(sim,'small',power=1,toughness=2)
        self.ready(sim)
        sim.declare_attackers([source.card.id,small.card.id])
        source.temporary_power=3
        snapshot=sim.event_game('combat')
        sim.send_to_destination(sim.players[0],source,snapshot=snapshot)
        small.counters=2
        self.drain(sim)
        self.assertEqual(small.counters,3)
        self.assertTrue(any(e['kind']=='mentor_counter' for e in sim.events))
        sim.invariant()
