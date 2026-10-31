"""Shared chosen-creature-type identity, lords and enter-with counters."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helpers


class ChosenTypeIdentityCounterChecks(unittest.TestCase):
    setUpClass = classmethod(helpers.EnchantmentChecks.setUpClass.__func__)
    tearDownClass = classmethod(helpers.EnchantmentChecks.tearDownClass.__func__)
    fixture = helpers.EnchantmentChecks.fixture
    put = helpers.EnchantmentChecks.put
    token = helpers.EnchantmentChecks.token

    def test_real_cards_new_names_and_parameters_are_composed(self):
        for name in ('Adaptive Automaton', 'Metallic Mimic'):
            raw = dict(self.lookup[name], name='Unseen tribal construct')
            parsed = s.import_diagnostic_card(self.rules, raw, 0, 'unseen', set())
            self.assertEqual(parsed.kind, 'creature', name)
            self.assertTrue(parsed.event_definition.chosen_type_entry)
            self.assertTrue(parsed.event_definition.chosen_type_identity)
            raw['oracleText'] += '\nDo an impossible thing.'
            self.assertEqual(s.import_diagnostic_card(self.rules, raw, 0, 'bad', set()).kind,
                             'unsupported')
        mimic = dict(self.lookup['Metallic Mimic'], name='Another unknown automaton')
        mimic['oracleText'] = mimic['oracleText'].replace(
            'an additional +1/+1 counter', 'two additional +1/+1 counters')
        parsed = s.import_diagnostic_card(self.rules, mimic, 0, 'two', set())
        self.assertEqual(parsed.event_definition.entry_counter_grants[0][1], 2)
        mimic['oracleText'] = mimic['oracleText'].replace('chosen type', 'unknown value')
        self.assertEqual(s.import_diagnostic_card(self.rules, mimic, 0, 'bad-two', set()).kind,
                         'unsupported')

    def test_automaton_acquires_chosen_type_but_buffs_other_creatures_only(self):
        sim, cards = self.fixture(['Adaptive Automaton'])
        goblin = self.token(sim, 'own goblin', subtypes=('Goblin',))
        self.token(sim, 'second goblin', subtypes=('Goblin',))
        elf = self.token(sim, 'own elf', subtypes=('Elf',))
        enemy = self.token(sim, 'enemy goblin', seat=1, subtypes=('Goblin',))
        source = self.put(sim, cards['Adaptive Automaton'])
        state = sim.event_game('main').battlefield[source.card.id]
        self.assertEqual(source.chosen_subtype, 'Goblin')
        self.assertIn('Goblin', state.definition.subtypes)
        self.assertIn('Construct', state.definition.subtypes)
        self.assertEqual(sim.effective_card(goblin).power, 3)
        self.assertEqual(sim.effective_card(elf).power, 2)
        self.assertEqual(sim.effective_card(enemy).power, 2)
        self.assertEqual(sim.effective_card(source).power, source.card.power)
        sim.send_to_destination(sim.players[0], source)
        self.assertEqual(sim.effective_card(goblin).power, 2)
        self.assertNotIn('Goblin', source.card.event_definition.subtypes)
        sim.invariant()

    def test_mimic_entry_replacement_scopes_and_counter_doubling(self):
        sim, cards = self.fixture(['Metallic Mimic', 'Doubling Season'])
        self.token(sim, 'first goblin', subtypes=('Goblin',))
        mimic = self.put(sim, cards['Metallic Mimic'])
        self.assertEqual(mimic.chosen_subtype, 'Goblin')
        self.put(sim, cards['Doubling Season'])
        own = self.token(sim, 'new goblin', subtypes=('Goblin',))
        elf = self.token(sim, 'new elf', subtypes=('Elf',))
        enemy = self.token(sim, 'enemy goblin', seat=1, subtypes=('Goblin',))
        self.assertEqual((own.counters, elf.counters, enemy.counters), (2, 0, 0))
        self.assertEqual(mimic.counters, 0)
        sim.send_to_destination(sim.players[0], mimic)
        later = self.token(sim, 'later goblin', subtypes=('Goblin',))
        self.assertEqual(later.counters, 0)
        self.assertEqual(own.counters, 2)  # Previously placed counters persist.
        sim.invariant()

    def test_chosen_type_counters_require_a_matching_choice(self):
        raw = dict(self.lookup['Metallic Mimic'], name='Unseen choice engine')
        raw['oracleText'] = raw['oracleText'].replace(
            'As this creature enters, choose a creature type.\n', '')
        self.assertEqual(s.import_diagnostic_card(self.rules, raw, 0, 'missing', set()).kind,
                         'unsupported')
        raw = dict(self.lookup['Adaptive Automaton'], name='Unknown type changer')
        raw['types'] = ['Artifact']
        self.assertEqual(s.import_diagnostic_card(self.rules, raw, 0, 'wrong-type', set()).kind,
                         'unsupported')


if __name__ == '__main__':
    unittest.main()
