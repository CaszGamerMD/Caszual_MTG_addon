"""Saved Mono-Red Howlsquad: subtype haste, forced combat token, and max-speed mana."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s


class SavedHowlsquadOracleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = s.RulesBridge()
        deck_path = Path(__file__).resolve().parents[1] / 'decks/14509839-mono-red-gobs.json'
        deck = json.loads(deck_path.read_text(encoding='utf-8'))
        cls.raw = next(c for c in deck['mainboard'] if c['name'] == 'Howlsquad Heavy')

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def parse(self, raw=None, uid='howlsquad'):
        return s.import_diagnostic_card(self.rules, raw or self.raw, 0, uid, {'Red'})

    def simulator(self, source, extra_cards=()):
        sim = s.Simulator(self.rules, 414,
                          decks=(s.demo_deck(0) + [source] + list(extra_cards),
                                 s.demo_deck(1)), diagnostic=True)
        sim.active = 0
        sim.turn = 1
        sim.phase = 'main'
        sim.stack.priority = 0
        sim.players[0].library.remove(source)
        permanent = s.Permanent(source)
        permanent.fresh = False
        sim.players[0].battlefield.append(permanent)
        return sim

    def test_saved_card_composes_all_three_rules_and_renamed_card_matches(self):
        real = self.parse()
        self.assertEqual(real.kind, 'creature')
        definition = real.event_definition
        self.assertIn('start_your_engines', definition.abilities)
        self.assertTrue(definition.scaled_mana_requires_max_speed)
        self.assertEqual(definition.scaled_mana_tap, 'count:R:Goblin:controller')
        self.assertEqual(len(definition.static_effects), 1)
        haste = definition.static_effects[0]
        self.assertEqual((haste.subject.relation, haste.subject.subtype, haste.grant),
                         ('controller', 'Goblin', 'haste'))
        self.assertTrue(haste.subject.other)
        self.assertEqual([t.event for t in definition.triggers], ['begin_combat'])
        token = definition.triggers[0].effect.token
        self.assertEqual((token.amount, token.power, token.toughness, token.subtypes),
                         (1, 1, 1, ('Goblin',)))
        self.assertTrue(token.must_attack_this_combat)

        renamed = dict(self.raw, name='Unfamiliar Goblin Engine')
        changed = self.parse(renamed, 'renamed-howlsquad')
        self.assertEqual(changed.kind, 'creature')
        self.assertEqual(changed.event_definition.scaled_mana_tap,
                         definition.scaled_mana_tap)
        self.assertEqual(changed.event_definition.triggers[0].effect.token,
                         token)

    def test_unknown_extra_text_still_rejects_the_complete_card(self):
        raw = dict(self.raw, oracleText=self.raw['oracleText'] + '\nGoblins can fly to the moon.')
        self.assertEqual(self.parse(raw, 'unknown-howlsquad-text').kind, 'unsupported')

    def test_speed_starts_once_increases_once_per_turn_and_persists(self):
        source = self.parse()
        sim = self.simulator(source)
        self.assertIsNone(sim.players[0].speed)
        sim.event_game('main')
        self.assertEqual(sim.players[0].speed, 1)
        sim.lose_life(1, 1, 'test opponent life loss')
        sim.lose_life(1, 2, 'second loss in same turn')
        self.assertEqual(sim.players[0].speed, 2)
        sim.turn = 2
        sim.lose_life(1, 1, 'next turn opponent life loss')
        self.assertEqual(sim.players[0].speed, 3)
        sim.turn = 3
        sim.lose_life(1, 1, 'third turn opponent life loss')
        self.assertEqual(sim.players[0].speed, 4)
        sim.turn = 4
        sim.lose_life(1, 1, 'max speed does not exceed four')
        self.assertEqual(sim.players[0].speed, 4)
        source_permanent = next(p for p in sim.players[0].battlefield if p.card.id == source.id)
        sim.send_to_destination(sim.players[0], source_permanent)
        self.assertEqual(sim.players[0].speed, 4)

    def test_max_speed_mana_activation_is_unavailable_until_speed_four(self):
        source = self.parse()

        def goblin(uid):
            definition = s.EventDefinition(uid, frozenset({'Creature'}),
                frozenset({'Goblin'}), False, 1, 1, frozenset())
            return s.Card(uid, uid, 'creature', traits='1;1;', power=1, toughness=1,
                          event_definition=definition)

        goblins = (goblin('goblin-a'), goblin('goblin-b'))
        sim = self.simulator(source, goblins)
        for card in goblins:
            player = sim.players[0]
            zone = next((cards for cards in (player.hand, player.library)
                         if card in cards), None)
            self.assertIsNotNone(zone, card.id)
            zone.remove(card)
            permanent = s.Permanent(card)
            permanent.fresh = False
            player.battlefield.append(permanent)
        self.assertFalse(any(identifier == source.id for identifier, _ in sim.mana_sources(0)))
        sim.players[0].speed = 4
        options = dict(sim.mana_sources(0))
        self.assertIn(source.id, options)
        red = s.mana_pool.COLORS.index('R')
        self.assertEqual(options[source.id][0][red], 3)
        sim.activate_scaled_mana(0, source.id, red)
        self.assertTrue(next(p for p in sim.players[0].battlefield if p.card.id == source.id).tapped)
        self.assertEqual(sim.players[0].mana_pool[red], 3)

    def test_begin_combat_token_enters_hasty_and_is_required_to_attack(self):
        source = self.parse()
        sim = self.simulator(source)
        game = sim.event_game('combat')
        events = game.begin_combat_triggers()
        self.assertEqual(len(events), 1)
        sim.resolve_entry_triggers(events, source)
        tokens = [p for p in sim.players[0].battlefield
                  if p.card.is_token and 'Goblin' in p.card.event_definition.subtypes]
        self.assertEqual(len(tokens), 1)
        token = tokens[0]
        self.assertIn('haste', sim.effective_card(token).traits)
        sim.phase = 'attack'
        sim.stack.priority = 0
        choices = sim.group_attack_choices(0)
        self.assertTrue(choices)
        self.assertTrue(all(token.card.id in choice.attack_ids for choice in choices))
        with self.assertRaises(ValueError):
            sim.declare_attackers([])
        sim.declare_attackers([token.card.id])
        sim.invariant()


if __name__ == '__main__':
    unittest.main()
