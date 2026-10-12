"""Static guards for Caszual MTG's four-slot full-length Staff Rack."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/main/java/dev/casz/caszualmtg"
ASSETS = ROOT / "src/main/resources/assets/caszual_mtg"
DATA = ROOT / "src/main/resources/data/caszual_mtg"


class StaffRackTests(unittest.TestCase):
    def test_four_staff_slots_preserve_item_data(self):
        source = (BASE / "StaffRackEntity.java").read_text()
        self.assertIn("SIZE=4", source)
        self.assertIn("ItemStack.CODEC", source)
        self.assertIn("staffs.get", source)
        self.assertIn('input.read("Staffs"', source)
        self.assertIn('output.store("Staffs"', source)
        self.assertIn("getUpdatePacket()", source)
        block = (BASE / "StaffRackBlock.java").read_text()
        self.assertIn("DataComponents.CONTAINER", block)
        self.assertIn("ItemContainerContents.fromItems(rack.contents())", block)
        self.assertIn("contents.copyInto(stored)", block)
        self.assertIn("popResource(level,pos,item)", block)
        self.assertIn("held.shrink(1)", block)
        menu = (BASE / "StaffRackMenu.java").read_text()
        self.assertIn("i<4", menu)
        self.assertIn("item.is(CaszualMtg.TARGETING_STAFF)", menu)
        self.assertIn("getMaxStackSize(){return 1;}", menu)

    def test_model_wall_facing_and_full_width(self):
        states = json.loads((ASSETS / "blockstates/staff_rack.json").read_text())
        self.assertEqual(set(states["variants"]), {
            "facing=north", "facing=east", "facing=south", "facing=west"
        })
        self.assertEqual({states["variants"][k]["y"] for k in states["variants"]},
                         {0, 90, 180, 270})
        block_model = json.loads((ASSETS / "models/block/staff_rack.json").read_text())
        self.assertGreaterEqual(len(block_model["elements"]), 11)
        for element in block_model["elements"]:
            self.assertTrue(all(0 <= v <= 16 for v in element["from"]))
            self.assertTrue(all(0 <= v <= 16 for v in element["to"]))
        item = json.loads((ASSETS / "items/staff_rack.json").read_text())
        self.assertEqual(item["model"]["model"], "caszual_mtg:item/staff_rack")
        recipe = json.loads((DATA / "recipe/staff_rack.json").read_text())
        self.assertEqual(recipe["result"]["id"], "caszual_mtg:staff_rack")
        loot = json.loads((DATA / "loot_table/blocks/staff_rack.json").read_text())
        self.assertEqual(loot["pools"], [], "Rack drops a single contents-preserving item in code")

    def test_hanging_staffs_are_raised_one_block(self):
        rack = (BASE / "StaffRackRenderer.java").read_text()
        self.assertIn("ItemStackRenderState[] staffs", rack)
        self.assertIn("ItemDisplayContext.FIXED", rack)
        self.assertIn("STAFF_HORIZONTAL_SCALE=.69f,STAFF_VERTICAL_SCALE=.92f", rack)
        self.assertIn("STAFF_VERTICAL_OFFSET=.38", rack)
        self.assertIn("2.0+4.0*i", rack)
        staff = json.loads((ASSETS / "models/item/targeting_staff.json").read_text())
        min_y = min(element["from"][1] for element in staff["elements"])
        max_y = max(element["to"][1] for element in staff["elements"])
        bottom = .38 + ((min_y - 8) / 16) * .92
        top = .38 + ((max_y - 8) / 16) * .92
        self.assertAlmostEqual(bottom, -1.0, delta=.04)
        self.assertGreater(top, 1.70, "Gem is raised beyond the old overlapping hooks")
        max_half_width = max((element["to"][0] - element["from"][0]) / 2
                             for element in staff["elements"]) * .69
        self.assertLess(max_half_width * 2, 4.0, "All 4 gems must fit across 16px rack")

    def test_registrations(self):
        mod = (BASE / "CaszualMtg.java").read_text()
        client = (BASE / "CaszualMtgClient.java").read_text()
        self.assertIn("STAFF_RACK_BE", mod)
        self.assertIn("STAFF_RACK_MENU", mod)
        self.assertIn("e.accept(STAFF_RACK)", mod)
        self.assertIn("StaffRackRenderer::new", client)
        self.assertIn("StaffRackScreen::new", client)


if __name__ == "__main__":
    unittest.main()
