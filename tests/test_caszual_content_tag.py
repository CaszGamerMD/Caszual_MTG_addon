"""Verify every Caszual MTG block/item joins the shared Caszual Content tag."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = ROOT / "src/main/resources/data/caszual_additions/tags/item/caszual_content.json"
SOURCE = ROOT / "src/main/java/dev/casz/caszualmtg/CaszualMtg.java"

EXPECTED = {
    "land_database", "token_database", "community_database",
    "deck_builder", "custom_deckbox", "hand_block",
    "deckbox_rack", "staff_rack", "counter", "targeting_staff",
}


class CaszualContentTagTest(unittest.TestCase):
    def test_all_registered_addon_items_are_tagged(self):
        tag = json.loads(TAG.read_text(encoding="utf-8"))
        self.assertFalse(tag["replace"], "Do not erase items supplied by Caszual Additions or other mods")
        values = tag["values"]
        self.assertEqual(len(values), len(set(values)), "No duplicate item entries")
        actual = {key.removeprefix("caszual_mtg:") for key in values}
        self.assertEqual(set(values), {f"caszual_mtg:{key}" for key in EXPECTED})
        self.assertEqual(actual, EXPECTED)

    def test_every_registered_item_name_has_a_tag_entry(self):
        source = SOURCE.read_text(encoding="utf-8")
        # Three database blocks are made through block(name, kind).
        database_ids = set(re.findall(r'block\("(\w+)",\s*[012]\)', source))
        other_ids = {
            "deck_builder", "hand_block", "custom_deckbox",
            "deckbox_rack", "staff_rack", "counter", "targeting_staff",
        }
        self.assertEqual(database_ids, {"land_database", "token_database", "community_database"})
        for item_id in other_ids:
            self.assertIn(f'id("{item_id}")', source)
        tag = json.loads(TAG.read_text(encoding="utf-8"))
        self.assertEqual(set(tag["values"]), {f"caszual_mtg:{key}" for key in database_ids | other_ids})

    def test_tag_belongs_to_additions_without_hard_mod_dependency(self):
        self.assertIn("data/caszual_additions/tags/item/", str(TAG))
        manifest = json.loads((ROOT / "src/main/resources/fabric.mod.json").read_text(encoding="utf-8"))
        self.assertNotIn("caszual_additions", manifest["depends"],
                         "The addon remains independently usable without Additions")


if __name__ == "__main__":
    unittest.main()
