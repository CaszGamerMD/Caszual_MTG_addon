"""Creature-type choices on entry drive dynamic, controller-scoped static bonuses."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
from oracle_abilities import compile_abilities
import test_enchantment_abilities as fixtures

class ChosenTypeChecks(unittest.TestCase):
    setUpClass=classmethod(fixtures.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EnchantmentChecks.tearDownClass.__func__)
    fixture=fixtures.EnchantmentChecks.fixture
    put=fixtures.EnchantmentChecks.put
    token=fixtures.EnchantmentChecks.token

    def test_full_oracle_unseen_name_and_unknown_clause_rejected(self):
        raw=dict(self.lookup['Rally the Ranks'],name='Unseen creature type anthem')
        card=s.import_diagnostic_card(self.rules,raw,0,'new',{'White'})
        self.assertEqual(card.kind,'enchantment')
        self.assertTrue(card.event_definition.chosen_type_entry)
        self.assertTrue(card.event_definition.static_effects[0].subject.chosen_subtype)
        raw['oracleText']+='\nChoose an impossible future.'
        self.assertEqual(s.import_diagnostic_card(self.rules,raw,0,'bad',{'White'}).kind,'unsupported')
        self.assertIsNone(compile_abilities('Creatures you control of the chosen type get +1/+1.'))
        self.assertIsNone(compile_abilities('As this enchantment enters, choose a creature type.'))
        self.assertIsNotNone(compile_abilities('As this enchantment enters, choose a creature type.\nCreatures you control of the chosen type get +2/+0.'))

    def test_chosen_type_is_recorded_and_updates_continuously(self):
        sim,cards=self.fixture(['Rally the Ranks'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        self.token(sim,'goblin-two',subtypes=('Goblin','Warrior'))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        source=self.put(sim,cards['Rally the Ranks'])
        self.assertEqual(source.chosen_subtype,'Goblin')
        self.assertEqual(sim.effective_card(goblin).power,3)
        self.assertEqual(sim.effective_card(elf).power,2)
        self.assertEqual(sim.effective_card(enemy).power,2)
        new_goblin=self.token(sim,'new-goblin',subtypes=('Goblin',))
        self.assertEqual(sim.effective_card(new_goblin).power,3)
        sim.send_to_destination(sim.players[0],source)
        self.assertEqual(sim.effective_card(goblin).power,2)
        sim.invariant()

    def test_no_creature_choice_uses_valid_fallback_and_stays_fixed(self):
        sim,cards=self.fixture(['Rally the Ranks'])
        source=self.put(sim,cards['Rally the Ranks'])
        self.assertEqual(source.chosen_subtype,'Human')
        goblin=self.token(sim,'later-goblin',subtypes=('Goblin',))
        human=self.token(sim,'later-human',subtypes=('Human',))
        self.assertEqual(sim.effective_card(goblin).power,2)
        self.assertEqual(sim.effective_card(human).power,3)
        sim.invariant()
