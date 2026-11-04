"""Exact saved-deck Oracle text regression for Mono-Red Equipment."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from card_events import parse_card
import simulator as simulator


DECK_PATH=Path(__file__).resolve().parents[1]/"decks"/"14509839-mono-red-gobs.json"


class SavedMonoRedEquipmentOracleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        deck=json.loads(DECK_PATH.read_text(encoding="utf-8"))
        cls.cards={card["name"]:card for card in deck["mainboard"]}

    def test_fire_and_ice_real_saved_oracle_compiles(self):
        raw=self.cards["Sword of Fire and Ice"]
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.attachment[2],
                         frozenset({"protection from red","protection from blue"}))
        self.assertEqual(parsed.equipped_player_hit_steps,
                         (("damage_equipment_target",2,None),("draw_cards",1,None)))
        with simulator.RulesBridge() as rules:
            imported=simulator.import_diagnostic_card(rules,raw,0,"saved-fire-ice",set())
        self.assertEqual(imported.kind,"equipment")
        self.assertIsNotNone(imported.event_definition)

    def test_body_and_mind_real_saved_oracle_compiles_and_preserves_subtype(self):
        raw=self.cards["Sword of Body and Mind"]
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.attachment[2],
                         frozenset({"protection from green","protection from blue"}))
        steps=parsed.equipped_player_hit_steps
        self.assertEqual(steps[0][0:2],("create_tokens",1))
        self.assertEqual(steps[0][2].power,2)
        self.assertEqual(steps[0][2].toughness,2)
        self.assertEqual(steps[0][2].colors,("Green",))
        self.assertEqual(steps[0][2].subtypes,("Wolf",))
        self.assertEqual(steps[1],("mill_damaged_player",10,None))
        with simulator.RulesBridge() as rules:
            imported=simulator.import_diagnostic_card(rules,raw,0,"saved-body-mind",set())
        self.assertEqual(imported.kind,"equipment")
        self.assertIsNotNone(imported.event_definition)

    def test_renamed_parameterized_body_and_mind_still_compiles(self):
        raw=dict(self.cards["Sword of Body and Mind"])
        raw["name"]="Unknown Green and Blue Blade"
        raw["oracleText"]=raw["oracleText"].replace("2/2 green Wolf","3/3 green Bear").replace(
            "mills ten cards","mills seven cards")
        parsed=parse_card(raw)
        self.assertTrue(parsed.supported,parsed.reason)
        self.assertEqual(parsed.equipped_player_hit_steps[0][2].subtypes,("Bear",))
        self.assertEqual(parsed.equipped_player_hit_steps[1][1],7)

    def test_unknown_extra_clause_remains_fail_closed(self):
        for name in ("Sword of Fire and Ice","Sword of Body and Mind"):
            raw=dict(self.cards[name])
            raw["oracleText"] += "\nYou win the game."
            self.assertFalse(parse_card(raw).supported,name)


if __name__=="__main__":
    unittest.main()
