"""Static subtype-based mandatory attacks compose with upkeep token creation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as fixtures


class MandatoryTribalAttackChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token
    drain=fixtures.EnchantmentChecks.drain

    def test_real_unseen_full_program_and_reject_unknown_clause(self):
        raw=dict(self.lookup['Goblin Assault'],name='Unknown tribal assault')
        card=s.import_diagnostic_card(self.rules,raw,0,'unseen',{'Red'})
        self.assertEqual(card.kind,'enchantment')
        self.assertTrue(card.event_definition.static_effects[0].must_attack)
        self.assertEqual(card.event_definition.triggers[0].event,'upkeep')
        raw['oracleText']+='\nCreatures you control fly to the moon.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'Red'}).kind,'unsupported')
        from oracle_abilities import compile_abilities
        self.assertIsNotNone(compile_abilities('Other Elf creatures you control attack each combat if able.'))
        self.assertIsNone(compile_abilities('Elf creatures attack each combat if able, unless a mystery happens.'))

    def test_required_attacks_apply_to_both_players_but_only_if_able(self):
        sim,cards=self.fixture(['Goblin Assault'])
        ally=self.token(sim,'ally-goblin',subtypes=('Goblin',))
        enemy=self.token(sim,'enemy-goblin',seat=1,subtypes=('Goblin',))
        elf=self.token(sim,'friendly-elf',subtypes=('Elf',))
        tapped=self.token(sim,'tapped-goblin',subtypes=('Goblin',));tapped.tapped=True
        source=self.put(sim,cards['Goblin Assault'])
        sim.active=0;sim.phase='attack';sim.stack.priority=0
        choices=sim.group_attack_choices(0)
        self.assertTrue(choices)
        self.assertTrue(all(ally.card.id in choice.attack_ids for choice in choices))
        self.assertTrue(all(tapped.card.id not in choice.attack_ids for choice in choices))
        with self.assertRaises(ValueError):sim.declare_attackers([elf.card.id])
        sim.declare_attackers([ally.card.id])
        sim.invariant()
        sim,cards=self.fixture(['Goblin Assault'])
        enemy=self.token(sim,'enemy-goblin',seat=1,subtypes=('Goblin',))
        self.put(sim,cards['Goblin Assault'])
        sim.active=1;sim.phase='attack';sim.stack.priority=1
        self.assertTrue(all(enemy.card.id in choice.attack_ids for choice in sim.group_attack_choices(1)))

    def test_upkeep_token_is_real_hasty_goblin_and_source_removal_ends_requirement(self):
        sim,cards=self.fixture(['Goblin Assault'])
        source=self.put(sim,cards['Goblin Assault'])
        sim.active=0
        game=sim.event_game('upkeep');game.turn_player=0
        sim.resolve_entry_triggers(game.upkeep_triggers(),source.card)
        self.assertTrue(sim.stack.items)
        self.drain(sim)
        tokens=[item for item in sim.players[0].battlefield if item.card.is_token and
                'Goblin' in item.card.event_definition.subtypes]
        self.assertEqual(len(tokens),1)
        self.assertIn('haste',sim.effective_card(tokens[0]).traits)
        sim.phase='attack';sim.stack.priority=0
        self.assertTrue(all(tokens[0].card.id in choice.attack_ids for choice in sim.group_attack_choices(0)))
        sim.send_to_destination(sim.players[0],source)
        self.assertTrue(any(choice.kind=='pass' for choice in sim.group_attack_choices(0)))
        sim.invariant()
