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
        # Boxes are already positioned correctly: world renderer uses -facing.toYRot().
        # The wooden shelves must follow their rotation, not the reverse mapping.
        expected={"north":180,"east":90,"south":0,"west":270}
        self.assertEqual(len(states["multipart"]),8)
        for state in states["multipart"]:
            facing=state["when"]["facing"]
            self.assertEqual(state["apply"]["y"],expected[facing])
        source=(SRC/"DeckboxRackRenderer.java").read_text()
        self.assertIn("rotationDegrees(-state.facing.toYRot())",source)
        self.assertIn("4.0/16.0",source,"Stored minis must remain on their existing side")
        collision=(SRC/"DeckboxRackBlock.java").read_text()
        for signature in [
            "case NORTH -> Block.box(0,bottom,8,16,top,16)",
            "case SOUTH -> Block.box(0,bottom,0,16,top,8)",
            "case EAST -> Block.box(0,bottom,0,8,top,16)",
            "case WEST -> Block.box(8,bottom,0,16,top,16)"
        ]:
            self.assertIn(signature,collision)

    def test_shelf_trim_has_no_coplanar_top_faces(self):
        for suffix,base_top,trim_top in [("floor",3,4),("wall",10,11)]:
            model=json.loads((ASSETS/f"models/block/deckbox_rack_base_{suffix}.json").read_text())
            base,front,back=model["elements"]
            self.assertEqual(base["to"][1],base_top)
            self.assertEqual(front["from"][1],base_top)
            self.assertEqual(back["from"][1],base_top)
            self.assertEqual(front["to"][1],trim_top)
            self.assertEqual(back["to"][1],trim_top)
            self.assertEqual(front["to"][2],1)
            self.assertEqual(back["from"][2],7)

    def test_minis_do_not_sink_into_shelf(self):
        source=(SRC/"DeckboxRackRenderer.java").read_text()
        self.assertIn("4.75/16.0",source)
        mini_scale=.195
        mini_bottom=(4.75/16) - mini_scale/2
        shelf_top=3/16
        self.assertGreater(mini_bottom,shelf_top,"Miniature deckbox bottoms must clear plank face")

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
