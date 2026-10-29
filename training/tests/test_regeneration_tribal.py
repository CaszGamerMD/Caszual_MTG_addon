"""Tribal anthem and tap-to-regenerate: legal targets, replacement and expiry."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures

class TribalRegenerationChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def setup_auntie(self):
        sim,cards=self.fixture(['Mad Auntie'])
        source=self.put(sim,cards['Mad Auntie']);source.fresh=False
        return sim,source

    def test_full_oracle_renamed_subtype_parameters_and_unknown_remainder(self):
        raw=dict(self.lookup['Mad Auntie'],name='Unseen clan elder')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'a',{'Black'}).kind,'creature')
        raw['oracleText']=raw['oracleText'].replace('Goblin','Elf').replace('+1/+1','+2/+3')
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'b',{'Black'}).kind,'creature')
        raw['oracleText']+='\nDraw a card.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'c',{'Black'}).kind,'unsupported')

    def test_anthem_other_only_and_tap_cost_stack_shield(self):
        sim,source=self.setup_auntie()
        goblin=self.token(sim,'goblin',subtypes=('Goblin',),power=2,toughness=2)
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        self.assertEqual(sim.effective_card(goblin).power,3)
        self.assertEqual(sim.effective_card(source).power,2)
        self.assertEqual(sim.effective_card(enemy).power,2)
        self.assertIn('goblin',{c.target_permanent for c in sim.regenerate_choices(0)})
        self.assertNotIn(source.card.id,{c.target_permanent for c in sim.regenerate_choices(0)})
        sim.activate_regenerate(0,source.card.id,goblin.card.id)
        self.assertTrue(source.tapped);self.assertEqual(goblin.regeneration_shields,0)
        with self.assertRaises(ValueError):sim.activate_regenerate(0,source.card.id,goblin.card.id)
        self.drain(sim);self.assertEqual(goblin.regeneration_shields,1)
        sim.invariant()

    def test_source_can_leave_after_activation_and_shield_prevents_destruction_once(self):
        sim,source=self.setup_auntie()
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        sim.activate_regenerate(0,source.card.id,goblin.card.id)
        sim.send_to_destination(sim.players[0],source)
        self.drain(sim)
        self.assertEqual(goblin.regeneration_shields,1)
        spell=s.Card('destroy','Destroy','removal_spell',removal='destroy')
        sim.destroy_batch(((0,goblin),),spell)
        self.assertIn(goblin,sim.players[0].battlefield)
        self.assertTrue(goblin.tapped)
        self.assertEqual(goblin.regeneration_shields,0)
        sim.destroy_batch(((0,goblin),),spell)
        self.assertNotIn(goblin,sim.players[0].battlefield)
        sim.invariant()

    def test_regeneration_does_not_prevent_zero_toughness_or_exile(self):
        sim,source=self.setup_auntie();goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        goblin.regeneration_shields=1;goblin.temporary_toughness=-5
        sim.resolve_entry_triggers(sim.state_based_actions(),source.card)
        self.assertNotIn(goblin,sim.players[0].battlefield)
        sim,source=self.setup_auntie();goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        goblin.regeneration_shields=1
        sim.send_to_destination(sim.players[0],goblin,to_exile=True)
        self.assertNotIn(goblin,sim.players[0].battlefield)
        self.assertNotIn(goblin.card,sim.players[0].exile)  # Tokens cease to exist.
        sim.invariant()

    def test_cannot_be_regenerated_sweep_bypasses_shield(self):
        sim,source=self.setup_auntie();goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        goblin.regeneration_shields=1
        raw=dict(name='Unseen sweeper',types=['Sorcery'],manaCost='{2}{B}{B}',
                 oracleText="Destroy all creatures. They can't be regenerated.")
        spell=s.import_diagnostic_card(self.rules,raw,0,'sweep',{'Black'})
        self.assertTrue(spell.removal_no_regenerate)
        sim.destroy_batch(((0,goblin),),spell)
        self.assertNotIn(goblin,sim.players[0].battlefield)
        sim.invariant()

    def test_fizzle_and_end_of_turn_expiry(self):
        sim,source=self.setup_auntie();goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        sim.activate_regenerate(0,source.card.id,goblin.card.id)
        goblin.temporary_abilities=frozenset({'shroud'})
        self.drain(sim)
        self.assertEqual(goblin.regeneration_shields,0)
        goblin.temporary_abilities=frozenset()
        goblin.regeneration_shields=2
        sim.phase='cleanup';sim._step()
        self.assertEqual(goblin.regeneration_shields,0)
        sim.invariant()

    def test_combat_regeneration_removes_blocker_and_clears_damage(self):
        sim,source=self.setup_auntie()
        blocker=self.token(sim,'blocker',seat=0,subtypes=('Goblin',),power=2,toughness=2)
        blocker.regeneration_shields=1
        attacker=self.token(sim,'attacker',seat=1,power=5,toughness=5)
        sim.active=1;sim.stack.active=1;sim.stack.priority=1;sim.phase='attack'
        sim.declare_attackers([attacker.card.id]);sim.declare_blockers({attacker.card.id:[blocker.card.id]})
        sim.group_damage_step();self.drain(sim)
        self.assertIn(blocker,sim.players[0].battlefield)
        self.assertTrue(blocker.tapped)
        self.assertEqual(blocker.marked_damage,0)
        self.assertEqual(blocker.regeneration_shields,0)
        sim.invariant()
