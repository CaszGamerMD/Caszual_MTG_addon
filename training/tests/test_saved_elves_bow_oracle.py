"""Saved Lupitas Elves Bow of Nylea: attacking deathtouch and four tap modes."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s


class SavedBowOfNyleaOracleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = s.RulesBridge()
        path = Path(__file__).resolve().parents[1] / 'decks/14435337-lupitas-elves.json'
        deck = json.loads(path.read_text(encoding='utf-8'))
        cls.raw = next(c for c in deck['mainboard'] if c['name'] == 'Bow of Nylea')

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def parse(self, raw=None, uid='bow-of-nylea'):
        return s.import_diagnostic_card(self.rules, raw or self.raw, 0, uid, {'Green'})

    def creature(self, uid, *, flying=False):
        return s.Card(uid, uid, 'creature', power=2, toughness=2, traits='2;2;' + ('flying' if flying else ''),
            event_definition=s.EventDefinition(uid, frozenset({'Creature'}), frozenset({'Elf'}),
                False, 2, 2, frozenset({'flying'} if flying else ())))

    def fixture(self, extra_cards=(), graveyard=()):
        bow = self.parse()
        sim = s.Simulator(self.rules, 177,
            decks=(s.demo_deck(0) + [bow] + list(extra_cards), s.demo_deck(1)), diagnostic=True)
        sim.active = 0
        sim.turn = 1
        sim.phase = 'main'
        sim.manual_priority = True
        sim.stack.priority = 0
        sim.players[0].mana_pool = [0, 0, 0, 0, 1, 1]
        p = sim.players[0]
        zone = next(cards for cards in (p.hand, p.library) if bow in cards)
        zone.remove(bow)
        source = s.Permanent(bow, fresh=False)
        p.battlefield.append(source)
        for card in graveyard:
            for zone in (p.hand, p.library):
                if card in zone:
                    zone.remove(card)
            p.graveyard.append(card)
        return sim, bow, source

    def resolve(self, sim):
        self.assertTrue(sim.stack.items)
        sim.pass_priority(0)
        sim.pass_priority(1)

    def test_saved_card_parses_static_grant_and_all_four_modes(self):
        bow = self.parse()
        self.assertEqual(bow.kind, 'artifact')
        definition = bow.event_definition
        self.assertEqual(len(definition.static_effects), 1)
        effect = definition.static_effects[0]
        self.assertTrue(effect.subject.attacking)
        self.assertEqual((effect.grant, effect.subject.relation), ('deathtouch', 'controller'))
        self.assertEqual(definition.modal_activation.cost, '{1}{G}')
        self.assertEqual([mode.operation for mode in definition.modal_activation.modes],
            ['counter_creature', 'damage_flying_creature', 'gain_life', 'bottom_graveyard_cards'])

    def test_renamed_card_uses_same_grammar_and_unknown_extra_text_fails_closed(self):
        raw = dict(self.raw, name='Unfamiliar Ranger Bow')
        raw['oracleText'] = raw['oracleText'].replace('Bow of Nylea', raw['name'])
        self.assertEqual(self.parse(raw, 'renamed-bow').kind, 'artifact')
        raw['oracleText'] += '\nCreatures you control can teleport.'
        self.assertEqual(self.parse(raw, 'unrecognized-bow').kind, 'unsupported')

    def test_counter_mode_targets_creature_and_resolves_one_counter(self):
        target = self.creature('target-creature')
        sim, bow, source = self.fixture((target,))
        p = sim.players[0]
        zone = next(cards for cards in (p.hand, p.library) if target in cards)
        zone.remove(target)
        p.battlefield.append(s.Permanent(target))
        choices = [c for c in sim.modal_activation_choices(0)
                   if c.activation_index == 0 and c.target_permanent == target.id]
        self.assertEqual(len(choices), 1)
        sim.activate_modal_mode(0, bow.id, 0, target.id)
        self.assertTrue(source.tapped)
        self.resolve(sim)
        self.assertEqual(next(p for p in sim.players[0].battlefield if p.card.id == target.id).counters, 1)
        sim.invariant()

    def test_damage_mode_is_limited_to_flying_creatures(self):
        flying = self.creature('flying-target', flying=True)
        grounded = self.creature('ground-target', flying=False)
        sim, bow, _ = self.fixture((flying, grounded))
        p = sim.players[0]
        for card in (flying, grounded):
            zone = next(cards for cards in (p.hand, p.library) if card in cards)
            zone.remove(card)
            p.battlefield.append(s.Permanent(card))
        choices = [c for c in sim.modal_activation_choices(0) if c.activation_index == 1]
        self.assertEqual([c.target_permanent for c in choices], [flying.id])
        sim.activate_modal_mode(0, bow.id, 1, flying.id)
        self.resolve(sim)
        self.assertFalse(any(p.card.id == flying.id for p in sim.players[0].graveyard))
        self.assertFalse(any(p.card.id == flying.id for p in sim.players[0].battlefield))
        self.assertTrue(any(p.card.id == grounded.id for p in sim.players[0].battlefield))
        sim.invariant()

    def test_life_mode_gains_three_life_and_needs_no_target(self):
        sim, bow, _ = self.fixture()
        sim.players[0].life = 20
        self.assertTrue(any(c.activation_index == 2 and not c.target_permanent
                            for c in sim.modal_activation_choices(0)))
        sim.activate_modal_mode(0, bow.id, 2)
        self.resolve(sim)
        self.assertEqual(sim.players[0].life, 23)
        sim.invariant()

    def test_graveyard_mode_moves_up_to_four_target_cards_to_library_bottom(self):
        cards = [s.Card('grave-' + str(i), 'Grave card ' + str(i), 'creature',
                        power=1, toughness=1, printed_types=('Creature',))
                 for i in range(5)]
        sim, bow, _ = self.fixture(cards, graveyard=cards)
        choices = [c for c in sim.modal_activation_choices(0) if c.activation_index == 3]
        self.assertTrue(any(len(c.tap_ids) == 0 for c in choices))
        self.assertTrue(any(len(c.tap_ids) == 4 for c in choices))
        selected = tuple(card.id for card in cards[:4])
        sim.activate_modal_mode(0, bow.id, 3, graveyard_ids=selected)
        self.resolve(sim)
        self.assertEqual([card.id for card in sim.players[0].library[:4]], list(selected))
        self.assertEqual([card.id for card in sim.players[0].graveyard], [cards[4].id])
        sim.invariant()

    def test_mode_with_newly_illegal_target_fizzles_at_resolution(self):
        target = self.creature('target-to-remove')
        sim, bow, _ = self.fixture((target,))
        player = sim.players[0]
        zone = next(cards for cards in (player.hand, player.library) if target in cards)
        zone.remove(target)
        player.battlefield.append(s.Permanent(target))
        sim.activate_modal_mode(0, bow.id, 0, target.id)
        permanent = next(p for p in player.battlefield if p.card.id == target.id)
        player.battlefield.remove(permanent)
        player.graveyard.append(target)
        self.resolve(sim)
        self.assertEqual(next((p.counters for p in player.battlefield if p.card.id == target.id), 0), 0)
        sim.invariant()


if __name__ == '__main__':
    unittest.main()
