"""Chair facing bounds and tabletop card tap/untap regression checks."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/"src/main/java/dev/casz/caszualmtg"
MODEL=ROOT/"src/main/resources/assets/caszual_mtg/models/block/material_chair.json"

class ChairAndTapTests(unittest.TestCase):
 def test_chair_shape_has_same_cuboids_as_wooden_model(self):
  source=(JAVA/"ChairBlock.java").read_text(encoding="utf-8")
  model=json.loads(MODEL.read_text(encoding="utf-8"))
  # Match every wooden seat, leg and backrest cuboid, including the top rail.
  for item in model["elements"]:
   start=",".join(str(n) for n in item["from"])
   end=",".join(str(n) for n in item["to"])
   self.assertIn(f"Block.box({start},{end})",source)
  for token in ("NORTH_SHAPE","EAST_SHAPE","SOUTH_SHAPE","WEST_SHAPE",
                "rotateClockwise(NORTH_SHAPE)","rotateClockwise(EAST_SHAPE)",
                "rotateClockwise(SOUTH_SHAPE)","case NORTH -> NORTH_SHAPE",
                "case EAST -> EAST_SHAPE","case SOUTH -> SOUTH_SHAPE",
                "case WEST -> WEST_SHAPE","getCollisionShape","shapeFor(state)"):
   self.assertIn(token,source)
  state=json.loads((ROOT/"src/main/resources/assets/caszual_mtg/blockstates/material_chair.json").read_text())
  self.assertEqual({(p["when"]["facing"],p["apply"]["y"]) for p in state["multipart"] if "cushion" not in p["when"]},
   {("north",0),("east",90),("south",180),("west",270)})

 def test_tapped_cards_rotate_and_are_clickable_in_new_bounds(self):
  screen=(JAVA/"TabletopScreen.java").read_text(encoding="utf-8")
  for token in ("if(c.tapped())","pose.pushMatrix()","pose.rotate((float)(Math.PI/2.0))",
                "g.pose().popMatrix()","int left=c.tapped()?x+(w-h)/2:x",
                "int top=c.tapped()?y+(h-w)/2:y",
                "int visualW=c.tapped()?h:w","int visualH=c.tapped()?w:h",
                'button("Untap All"','action("untap_all",0)'):
   self.assertIn(token,screen)

 def test_untap_all_respects_card_ownership(self):
  logic=(JAVA/"TabletopLogic.java").read_text(encoding="utf-8")
  self.assertIn('case "untap_all"',logic)
  self.assertIn("player.getUUID().toString()",logic)
  self.assertIn("for(TabletopBlockEntity table:c.tiles)",logic)
  self.assertIn("owner.equals(card.owner())&&card.tapped()",logic)
  self.assertIn("table.replace(card.tapped(false))",logic)
  self.assertIn('"untap_all","hide"',logic)

if __name__=="__main__":unittest.main()
