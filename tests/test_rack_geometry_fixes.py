"""Rack orientation, item-height, and coplanar-surface regression checks."""
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"src/main/resources/assets/caszual_mtg"
SRC=ROOT/"src/main/java/dev/casz/caszualmtg"


class RackGeometryFixes(unittest.TestCase):
    def test_wall_and_floor_shelves_follow_existing_box_renderer_rotation(self):
        states=json.loads((ASSETS/"blockstates/deckbox_rack.json").read_text())
        expected={"north":180,"east":90,"south":0,"west":270}
        self.assertEqual(len(states["multipart"]),8)
        for state in states["multipart"]:
            facing=state["when"]["facing"]
            self.assertEqual(state["apply"]["y"],expected[facing])
        source=(SRC/"DeckboxRackRenderer.java").read_text()
        self.assertIn("rotationDegrees(-state.facing.toYRot())",source)
        self.assertIn("4.0/16.0",source,"Miniatures stay centered 4px from the rear")
        collision=(SRC/"DeckboxRackBlock.java").read_text()
        for signature in [
            "case NORTH -> Block.box(0,bottom,10,16,top,16)",
            "case SOUTH -> Block.box(0,bottom,0,16,top,6)",
            "case EAST -> Block.box(10,bottom,0,16,top,16)",
            "case WEST -> Block.box(0,bottom,0,6,top,16)"
        ]:
            self.assertIn(signature,collision)

    def test_ledge_is_two_pixels_thick_six_deep_without_overlapping_faces(self):
        for suffix,base_y in [("floor",0),("wall",7)]:
            model=json.loads((ASSETS/f"models/block/deckbox_rack_base_{suffix}.json").read_text())
            self.assertEqual(len(model["elements"]),3)
            rear,wood,front=model["elements"]
            for element in model["elements"]:
                self.assertEqual(element["from"][0],0)
                self.assertEqual(element["to"][0],16)
                self.assertEqual(element["from"][1],base_y)
                self.assertEqual(element["to"][1],base_y+2)
            self.assertEqual((rear["from"][2],rear["to"][2]),(0,.75))
            self.assertEqual((wood["from"][2],wood["to"][2]),(.75,5.25))
            self.assertEqual((front["from"][2],front["to"][2]),(5.25,6))
            # Interior faces touching another solid are removed entirely:
            # nothing renders twice at any common boundary.
            self.assertNotIn("south",rear["faces"])
            self.assertNotIn("north",wood["faces"])
            self.assertNotIn("south",wood["faces"])
            self.assertNotIn("north",front["faces"])
            self.assertEqual(wood["faces"]["up"]["texture"],"#shelf")
            self.assertEqual(front["faces"]["up"]["texture"],"#edge")

    def test_minis_rest_on_shelf_not_behind_or_inside_it(self):
        source=(SRC/"DeckboxRackRenderer.java").read_text()
        self.assertIn("3.65/16.0",source)
        self.assertIn("4.0/16.0",source)
        mini_scale=.195
        mini_bottom_px=3.65-mini_scale*8
        shelf_top_px=2
        clearance=mini_bottom_px-shelf_top_px
        self.assertGreater(clearance,0,"Miniatures must not penetrate wood")
        self.assertLess(clearance,.2,"Miniature boxes must rest visually on shelf, not float")
        # The FIXED item occupies approximately +/-1.56 px in Z at this scale.
        mini_back=4-mini_scale*8
        mini_front=4+mini_scale*8
        self.assertGreater(mini_back,0,"Miniature cannot protrude through back of ledge")
        self.assertLess(mini_front,6,"Miniature cannot float off front of ledge")
        self.assertAlmostEqual((7+3.65-mini_scale*8)-9,clearance,places=4)

    def test_staff_trim_and_gems_no_longer_overlap(self):
        model=json.loads((ASSETS/"models/block/staff_rack.json").read_text())
        wood,low_trim,high_trim=model["elements"][:3]
        self.assertEqual(wood["from"][1],low_trim["to"][1])
        self.assertEqual(wood["to"][1],high_trim["from"][1])
        self.assertLess(low_trim["to"][1],high_trim["from"][1])
        source=(SRC/"StaffRackRenderer.java").read_text()
        self.assertIn("STAFF_VERTICAL_OFFSET=.38",source)
        staff=json.loads((ASSETS/"models/item/targeting_staff.json").read_text())
        min_y=min(el["from"][1] for el in staff["elements"])
        max_y=max(el["to"][1] for el in staff["elements"])
        bottom=.38 + (min_y-8)/16*.92
        gem_bottom=.38 + (26.5-8)/16*.92
        self.assertAlmostEqual(bottom,-1.0,delta=.04)
        self.assertGreater(gem_bottom,1.0,"Gem must sit clearly above the rack's metal hooks")


if __name__=="__main__":
    unittest.main()
