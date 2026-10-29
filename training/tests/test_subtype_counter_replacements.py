"""Generic creature-type counter replacements compose with other replacements."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import simulator as s
import test_enchantment_abilities as helper

class SubtypeCounterReplacementChecks(unittest.TestCase):
    setUpClass=classmethod(helper.EnchantmentChecks.setUpClass.__func__)
    tearDownClass=classmethod(helper.EnchantmentChecks.tearDownClass.__func__)
    fixture=helper.EnchantmentChecks.fixture
    put=helper.EnchantmentChecks.put
    token=helper.EnchantmentChecks.token

    def test_mauhur_and_renamed_tribes_parse_strictly(self):
        raw=dict(self.lookup['Mauhúr, Uruk-hai Captain'],name='Unknown captain')
        card=s.import_diagnostic_card(self.rules,raw,0,'unknown',set())
        self.assertEqual(card.kind,'creature')
        self.assertIn('menace',card.event_definition.abilities)
        replacement=card.event_definition.counter_replacements[0]
        self.assertEqual(replacement,('plus',1,'controlled_subtypes','any',('Army','Goblin','Orc')))
        other=dict(raw,oracleText='Menace\nIf one or more +1/+1 counters would be put on an Elf, Faerie, or Goblin you control, that many plus one +1/+1 counters are put on it instead.')
        parsed=s.import_diagnostic_card(self.rules,other,0,'changed',set())
        self.assertEqual(parsed.event_definition.counter_replacements[0][-1],('Elf','Faerie','Goblin'))
        other['oracleText']+='\nUnknown instruction.'
        self.assertEqual(s.import_diagnostic_card(self.rules,other,0,'bad',set()).kind,'unsupported')

    def test_subtype_scoping_and_opponent_exclusion(self):
        sim,cards=self.fixture(['Mauhúr, Uruk-hai Captain'])
        self.put(sim,cards['Mauhúr, Uruk-hai Captain'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        elf=self.token(sim,'elf',subtypes=('Elf',))
        enemy=self.token(sim,'enemy',seat=1,subtypes=('Goblin',))
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(goblin.card.id,1),2)
        self.assertEqual(game.counter_amount(elf.card.id,1),1)
        self.assertEqual(game.counter_amount(enemy.card.id,1),1)
        self.assertEqual(game.counter_amount(goblin.card.id,0),0)
        sim.invariant()

    def test_counter_plus_then_doubling_replacements(self):
        sim,cards=self.fixture(['Mauhúr, Uruk-hai Captain','Branching Evolution'])
        self.put(sim,cards['Mauhúr, Uruk-hai Captain'])
        self.put(sim,cards['Branching Evolution'])
        goblin=self.token(sim,'goblin',subtypes=('Goblin',))
        game=sim.event_game('main')
        self.assertEqual(game.counter_amount(goblin.card.id,1),4)
        self.assertEqual(game.counter_amount(goblin.card.id,2),6)
        sim.invariant()
