"""Shared keyword grants, group blocking restrictions and saddled triggers."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_final_seven as fixtures


class MenaceMountChecks(unittest.TestCase):
    fixture = fixtures.FinalSevenChecks.fixture
    drain = fixtures.FinalSevenChecks.drain
    token = fixtures.FinalSevenChecks.token
    ready = fixtures.FinalSevenChecks.ready
    damage = fixtures.FinalSevenChecks.damage
    setUpClass = classmethod(fixtures.FinalSevenChecks.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.FinalSevenChecks.tearDownClass.__func__)

    def test_four_actual_cards_and_unfamiliar_names_compile_strictly(self):
        for name in ('Goblin War Drums', 'True Conviction', 'Quilled Charger', 'Bridled Bighorn'):
            for label in (name, 'Unfamiliar rules carrier'):
                raw = dict(self.lookup[name], name=label)
                card = s.import_diagnostic_card(self.rules, raw, 0, 'test', set())
                self.assertNotEqual(card.kind, 'unsupported', name)
                raw['oracleText'] += '\nDraw an extra card at random.'
                self.assertEqual(s.import_diagnostic_card(self.rules, raw, 0, 'bad', set()).kind, 'unsupported')

    def menace_combat(self, blockers=2):
        sim, _ = self.fixture(['Goblin War Drums'])
        self.token(sim, 'attacker', power=4, toughness=4)
        for i in range(blockers):
            self.token(sim, 'blocker' + str(i), 1, power=1, toughness=1)
        self.ready(sim)
        sim.declare_attackers(['attacker'])
        return sim

    def test_menace_rejects_one_blocker_without_mutating_combat(self):
        sim = self.menace_combat()
        with self.assertRaises(ValueError):
            sim.declare_blockers({'attacker': ['blocker0']})
        self.assertEqual(sim.phase, 'block')
        self.assertEqual(sim.group_combat['blocks'], {})
        sim.declare_blockers({'attacker': ['blocker0', 'blocker1']})
        self.damage(sim)
        self.assertEqual(sim.players[1].life, 40)
        sim.invariant()

    def test_menace_can_be_unblocked_and_policy_never_offers_single_blocker(self):
        for count in (1, 2, 3):
            sim = self.menace_combat(count)
            choices = sim.group_block_choices(1)
            self.assertTrue(choices)
            for choice in choices:
                for _, blockers in choice.blocks:
                    self.assertGreaterEqual(len(blockers), 2)
            self.assertEqual(any(choice.blocks for choice in choices), count >= 2)
            sim.declare_blockers({})
            self.damage(sim)
            self.assertEqual(sim.players[1].life, 36)

    def test_menace_rechecks_grants_at_block_declaration(self):
        sim = self.menace_combat()
        drums = next(p for p in sim.players[0].battlefield if p.card.name == 'Goblin War Drums')
        sim.send_to_destination(sim.players[0], drums)
        sim.declare_blockers({'attacker': ['blocker0']})
        self.damage(sim)
        self.assertEqual(sim.players[1].life, 40)

    def test_removing_blockers_does_not_undo_a_legal_menace_block(self):
        sim = self.menace_combat()
        sim.declare_blockers({'attacker': ['blocker0', 'blocker1']})
        for blocker in list(sim.players[1].battlefield):
            sim.send_to_destination(sim.players[1], blocker)
        self.damage(sim)
        self.assertEqual(sim.players[1].life, 40)
        sim.invariant()

    def test_menace_is_intrinsic_and_does_not_bypass_flying(self):
        raw = dict(name='Unknown evasive creature', types=['Creature'], subTypes=[], power='2', toughness='2', manaCost='{B}', oracleText='Flying, menace')
        card = s.import_diagnostic_card(self.rules, raw, 0, 'intrinsic', set())
        self.assertEqual(card.kind, 'creature')
        sim, _ = self.fixture([])
        sim.enter_creature(replace(card, is_token=True), sim.players[0])
        sim.players[0].battlefield[-1].fresh = False
        self.token(sim, 'ground', 1)
        self.token(sim, 'air', 1, keywords=('flying',))
        self.ready(sim)
        sim.declare_attackers([card.id])
        with self.assertRaises(ValueError):
            sim.declare_blockers({card.id: ['ground', 'air']})
        with self.assertRaises(ValueError):
            sim.declare_blockers({card.id: ['air', 'air']})

    def test_combined_grants_apply_to_both_damage_steps(self):
        sim, _ = self.fixture(['True Conviction'])
        self.token(sim, 'attacker', power=3, toughness=3)
        self.token(sim, 'enemy', 1)
        game = sim.event_game('combat')
        self.assertFalse(game.has(game.battlefield['enemy'], 'lifelink'))
        self.ready(sim)
        sim.declare_attackers(['attacker'])
        sim.declare_blockers({})
        self.damage(sim)
        self.assertEqual(sim.players[1].life, 34)
        self.assertEqual(sim.players[0].life, 46)
        sim.invariant()

    def test_saddled_tokens_require_saddled_attack_and_enter_normally(self):
        for saddled in (False, True):
            sim, cards = self.fixture(['Bridled Bighorn'])
            mount = next(p for p in sim.players[0].battlefield if p.card.id == cards['Bridled Bighorn'].id)
            mount.saddled = saddled
            self.ready(sim)
            sim.declare_attackers([mount.card.id])
            self.assertEqual(len(sim.stack.items), int(saddled))
            self.drain(sim)
            tokens = [p for p in sim.players[0].battlefield if p.card.is_token]
            self.assertEqual(len(tokens), int(saddled))
            if tokens:
                self.assertFalse(tokens[0].tapped)
                self.assertNotIn(tokens[0].card.id, sim.group_combat['attackers'])
            sim.invariant()

    def test_saddled_token_trigger_survives_source_leaving(self):
        sim, cards = self.fixture(['Bridled Bighorn'])
        mount = next(p for p in sim.players[0].battlefield if p.card.id == cards['Bridled Bighorn'].id)
        mount.saddled = True
        self.ready(sim)
        sim.declare_attackers([mount.card.id])
        sim.send_to_destination(sim.players[0], mount)
        self.drain(sim)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token]), 1)
        sim.invariant()

    def test_saddled_token_condition_is_checked_when_attacking(self):
        sim, cards = self.fixture(['Bridled Bighorn'])
        mount = next(p for p in sim.players[0].battlefield if p.card.id == cards['Bridled Bighorn'].id)
        mount.saddled = True
        self.ready(sim)
        sim.declare_attackers([mount.card.id])
        mount.saddled = False
        self.drain(sim)
        self.assertEqual(len([p for p in sim.players[0].battlefield if p.card.is_token]), 1)

    def test_saddled_menace_boost_resolves_on_stack_and_expires(self):
        sim, cards = self.fixture(['Quilled Charger'])
        mount = next(p for p in sim.players[0].battlefield if p.card.id == cards['Quilled Charger'].id)
        before = sim.effective_card(mount)
        mount.saddled = True
        self.ready(sim)
        sim.declare_attackers([mount.card.id])
        self.assertNotIn('menace', sim.effective_card(mount).traits)
        self.drain(sim)
        boosted = sim.effective_card(mount)
        self.assertEqual((boosted.power, boosted.toughness), (before.power + 1, before.toughness + 2))
        self.assertIn('menace', boosted.traits)
        game = sim.event_game('cleanup')
        game.cleanup()
        sim.sync_events(game)
        self.assertNotIn('menace', sim.effective_card(mount).traits)
        self.assertEqual(sim.effective_card(mount).power, before.power)
