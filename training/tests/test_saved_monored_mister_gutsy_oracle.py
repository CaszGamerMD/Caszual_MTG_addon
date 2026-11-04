"""Saved Mono-Red Mister Gutsy: cast counters and counter-scaled Junk death trigger."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s


class SavedMisterGutsyOracleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = s.RulesBridge()
        path = Path(__file__).resolve().parents[1] / 'decks/14509839-mono-red-gobs.json'
        deck = json.loads(path.read_text(encoding='utf-8'))
        cls.raw = next(c for c in deck['mainboard'] if c['name'] == 'Mister Gutsy')

    @classmethod
    def tearDownClass(cls):
        cls.rules.close()

    def parse(self, raw=None, uid='mister-gutsy'):
        return s.import_diagnostic_card(self.rules, raw or self.raw, 0, uid, {'Red'})

    def fixture(self, source, extra_cards=()):
        sim = s.Simulator(self.rules, 903,
            decks=(s.demo_deck(0) + [source] + list(extra_cards), s.demo_deck(1)),
            diagnostic=True)
        sim.active = 0
        sim.turn = 1
        sim.phase = 'main'
        sim.manual_priority = True
        sim.stack.priority = 0
        player = sim.players[0]
        zone = next((cards for cards in (player.hand, player.library) if source in cards), None)
        self.assertIsNotNone(zone)
        zone.remove(source)
        permanent = s.Permanent(source, fresh=False)
        player.battlefield.append(permanent)
        return sim, permanent

    def resolve_top(self, sim):
        self.assertTrue(sim.stack.items)
        sim.pass_priority(0)
        sim.pass_priority(1)

    def test_saved_card_imports_both_cast_and_death_abilities(self):
        card = self.parse()
        self.assertEqual(card.kind, 'creature')
        self.assertEqual([trigger.event for trigger in card.event_definition.triggers],
                         ['cast', 'dies'])
        cast, death = card.event_definition.triggers
        self.assertEqual(cast.subject.spell_type, 'aura_or_equipment')
        self.assertEqual(cast.effect.operation, 'self_counter')
        self.assertEqual(death.effect.operation, 'death_counter_junk_tokens')

    def test_renamed_card_shares_the_same_rules_without_name_dispatch(self):
        raw = dict(self.raw, name='Unfamiliar Scrap Automaton')
        self.assertEqual(self.parse(raw, 'unfamiliar-gutsy').kind, 'creature')
        self.assertEqual(self.parse(dict(raw, oracleText=raw['oracleText'] + '\\nIt can fly.'),
                                    'extra-unfamiliar-gutsy').kind, 'unsupported')

    def test_aura_and_equipment_casts_each_put_a_counter_on_mister_gutsy(self):
        source = self.parse()
        sim, permanent = self.fixture(source)
        fixtures = (
            s.Card('unseen-aura', 'Unseen Aura', 'spell',
                   printed_types=('Enchantment','Aura')),
            s.Card('unseen-equipment', 'Unseen Equipment', 'spell',
                   printed_types=('Artifact','Equipment')),
        )
        for spell in fixtures:
            events = sim.event_game('main').cast_triggers(spell,0)
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['operation'],'self_counter')
            sim.resolve_entry_triggers(events,source)
            self.resolve_top(sim)
        self.assertEqual(permanent.counters,2)
        sim.invariant()

    def test_dies_trigger_uses_last_known_plus_one_counters_and_creates_junk(self):
        source = self.parse()
        sim, permanent = self.fixture(source)
        permanent.counters = 3
        snapshot = sim.event_game('main')
        triggers = snapshot.death_triggers([source.id])
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]['operation'], 'death_counter_junk_tokens')
        self.assertEqual(triggers[0]['lastCounters'], 3)
        sim.send_to_destination(sim.players[0], permanent, snapshot=snapshot)
        sim.resolve_entry_triggers(triggers, source)
        self.resolve_top(sim)
        junk = [item for item in sim.players[0].battlefield if item.card.is_token and
                item.card.event_definition and 'Junk' in item.card.event_definition.subtypes]
        self.assertEqual(len(junk), 3)
        self.assertTrue(all(item.card.event_definition.junk_token_activation for item in junk))
        self.assertTrue(all('Artifact' in item.card.event_definition.types for item in junk))
        sim.invariant()

    def test_zero_counters_create_no_junk_tokens(self):
        source = self.parse()
        sim, permanent = self.fixture(source)
        snapshot = sim.event_game('main')
        triggers = snapshot.death_triggers([source.id])
        sim.send_to_destination(sim.players[0], permanent, snapshot=snapshot)
        sim.resolve_entry_triggers(triggers, source)
        self.resolve_top(sim)
        self.assertFalse(any(item.card.is_token and item.card.name == 'Junk'
                             for owner in sim.players for item in owner.battlefield))
        sim.invariant()

    def test_junk_taps_and_sacrifices_at_sorcery_speed_then_exiles_top_card(self):
        source = self.parse()
        top = s.Card('junk-top-card', 'Top card', 'creature', power=2, toughness=2,
                     mana_cost='{0}', printed_types=('Creature',))
        sim, _ = self.fixture(source, (top,))
        sim.players[0].library.remove(top) if top in sim.players[0].library else sim.players[0].hand.remove(top)
        sim.players[0].library.append(top)
        junk_definition = s.EventDefinition('Junk', frozenset({'Artifact'}), frozenset({'Junk'}),
            False, 0, 0, frozenset(), junk_token_activation=True)
        junk_card = s.Card('junk-token-test', 'Junk', 'artifact', event_definition=junk_definition,
                           is_token=True)
        junk = s.Permanent(junk_card)
        sim.players[0].battlefield.append(junk)
        choices = sim.token_ability_choices(0)
        self.assertTrue(any(choice.kind == 'activate_junk' and choice.card_id == junk_card.id
                            for choice in choices))
        sim.activate_junk(0, junk_card.id)
        self.assertFalse(any(item.card.id == junk_card.id for item in sim.players[0].battlefield))
        self.assertNotIn(top, sim.players[0].exile)
        self.resolve_top(sim)
        self.assertIn(top, sim.players[0].exile)
        self.assertIn(top, sim.permitted_exile_cards(0))
        self.assertTrue(any(choice.kind=='cast_exile' and choice.card_id==top.id
                            for choice in sim.legal(0)))
        self.assertEqual(sim.exile_cast_permissions[top.id], (0, sim.turn, ''))
        sim.cast_spell(0,top,exile_permission=True)
        self.assertNotIn(top,sim.players[0].exile)
        self.assertNotIn(top.id,sim.exile_cast_permissions)
        sim.invariant()

    def test_junk_permission_allows_a_land_play_at_normal_land_timing(self):
        source = self.parse()
        forest = s.Card('junk-top-forest', 'Forest', 'land',
            mana_production=(0,0,0,0,1,0),land_subtypes=('Forest',),basic_land=True)
        sim, _ = self.fixture(source, (forest,))
        player = sim.players[0]
        zone = next(cards for cards in (player.hand,player.library) if forest in cards)
        zone.remove(forest)
        player.library.append(forest)
        junk_definition = s.EventDefinition('Junk', frozenset({'Artifact'}), frozenset({'Junk'}),
            False, 0, 0, frozenset(), junk_token_activation=True)
        junk_card = s.Card('junk-land-test', 'Junk', 'artifact',event_definition=junk_definition,
                           is_token=True)
        sim.players[0].battlefield.append(s.Permanent(junk_card))
        sim.activate_junk(0,junk_card.id)
        self.resolve_top(sim)
        self.assertIn(forest,sim.permitted_exile_cards(0))
        self.assertTrue(any(choice.kind=='land_exile' and choice.card_id==forest.id
                            for choice in sim.legal(0)))
        sim.play_exiled_land(0,forest)
        self.assertFalse(any(card.id==forest.id for card in sim.players[0].exile))
        self.assertTrue(any(item.card.id==forest.id for item in sim.players[0].battlefield))
        self.assertEqual(sim.land_plays_this_turn,1)
        sim.invariant()

    def test_junk_activation_rejects_non_sorcery_timing(self):
        source = self.parse()
        sim, _ = self.fixture(source)
        junk_definition = s.EventDefinition('Junk', frozenset({'Artifact'}), frozenset({'Junk'}),
            False, 0, 0, frozenset(), junk_token_activation=True)
        junk_card = s.Card('junk-timing-test', 'Junk', 'artifact', event_definition=junk_definition,
                           is_token=True)
        sim.players[0].battlefield.append(s.Permanent(junk_card))
        sim.stack.push(1, ({'operation': 'noop'}, junk_card), 'Opponent spell')
        sim.stack.priority = 0
        with self.assertRaises(ValueError):
            sim.activate_junk(0, junk_card.id)


if __name__ == '__main__':
    unittest.main()
