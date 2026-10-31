"""Unfamiliar-card modal parsing and mode-selection safety."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modal_target_blocks import Mode, parse

class ModalTargetTests(unittest.TestCase):
    def test_abrade_structure_and_unknown_card_names(self):
        text = "Choose one —\n• Deal 3 damage to target creature.\n• Destroy target artifact."
        p = parse(text, ["Instant"])
        self.assertEqual(p.choose, 1)
        self.assertEqual(p.bind((0,)), (Mode("damage", "creature", 3),))
        self.assertEqual(p.bind((1,)), (Mode("destroy", "artifact"),))
        self.assertEqual(parse(text.replace("3 damage", "5 damage"), ["Instant"])
                         .bind((0,))[0].amount, 5)

    def test_choose_two_and_distinct_modes(self):
        text = ("Choose two —\n• Destroy target artifact.\n"
                "• Exile target enchantment.\n"
                "• Deal 4 damage to target creature.")
        p = parse(text, ["Sorcery"])
        self.assertEqual(p.bind((2, 0)),
                         (Mode("damage", "creature", 4), Mode("destroy", "artifact")))
        for selection in ((0,), (0, 0), (3, 1), (-1, 1), (True, 1), (1, 1, 2)):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError): p.bind(selection)

    def test_no_silent_partial_compilation(self):
        base = "Choose one —\n• Destroy target artifact."
        for extra in ("\n• Draw two cards.", "\nChoose a player.",
                      "\n• Destroy target artifact.", "\n• Deal 1001 damage to target creature."):
            self.assertIsNone(parse(base + extra, ["Instant"]))
        self.assertIsNone(parse("Destroy target artifact.", ["Instant"]))
        self.assertIsNone(parse(base, ["Creature"]))
        self.assertIsNone(parse("Choose two —\n• Destroy target artifact.", ["Sorcery"]))

if __name__ == "__main__":
    unittest.main()
